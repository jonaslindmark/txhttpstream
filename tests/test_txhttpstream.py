from twisted.internet import defer, task, error
import txhttpstream
from twisted.trial.unittest import TestCase
import tests
from nose import tools as nt
from itertools import imap

class Base(TestCase):

    def startTestServer(self, chunks, delay, add_delim=True):
        self.server = tests.startTestServer(8080, chunks, delay, add_delim=add_delim)

    def deferTearDown(self, ignored, result):
        if self.server is not None:
            return self.server.stop()
        return defer.succeed(None)


class TestGetStreamedPages(Base):
    def test_get_chunk_by_chunk(self):
        chunks = ["hej %d" % i for i in range(0,10)]
        self.startTestServer(chunks,0)
        received_chunks = []

        def verify():
            nt.assert_equal(chunks, received_chunks)

        def handleChunk(result):
            if result is None:
                verify()
                return
            (chunk, nextChunkDeferred) = result
            received_chunks.append(chunk)
            return nextChunkDeferred.addCallback(handleChunk)

        return txhttpstream.getStreamedPages("http://localhost:8080") \
                .addCallback(handleChunk)

    def test_handles_early_connection_failure(self):
        d = txhttpstream.getStreamedPages("http://idontexislkjlkjljs") \
                .addCallbacks(lambda ign: nt.assert_true(False))
        self.assertFailure(d, error.DNSLookupError)
        return d

    def test_handles_timeouts(self):
        self.startTestServer([""],1)
        d = txhttpstream.getStreamedPages("http://localhost:8080", timeout=0.01) \
                .addCallbacks(lambda ign: nt.assert_true(False))
        self.assertFailure(d, defer.TimeoutError)
        return d


class TestGetStreamedPagesIterator(Base):

    def _consume_iterator(self, iterator):
        results = []
        errors = []

        def collect_result(d):
            return d.addCallbacks(lambda result: results.append(result), lambda f: errors.append(f))

        work = imap(collect_result, iterator)
        ds = [task.coiterate(work) for i in range(0,10)]
        return defer.gatherResults(ds).addCallback(lambda ign: (results, errors))

    def _verify_failures(self, (results, failures), failure_type):
        nt.assert_equal(results, [])
        assert len(failures) > 0
        for f in failures:
            while f.check(defer.FirstError):
                f = f.value.subFailure
            nt.assert_equal(f.type, failure_type)

    def test_get_chunk_coiterate(self):
        chunks = ["hej %d" % i for i in range(0,10)]
        self.startTestServer(chunks,0)

        def verify((received_chunks, failures)):
            nt.assert_equal(failures, [])
            key = set(chunks)
            key.add(None)
            nt.assert_equal(key, set(received_chunks))

        iterator = txhttpstream.getStreamedPagesIterator("http://localhost:8080")
        return self._consume_iterator(iterator).addCallback(verify)

    def test_connection_error(self):
        iterator = txhttpstream.getStreamedPagesIterator("http://localhost:8080")
        return self._consume_iterator(iterator).addCallback(self._verify_failures, error.ConnectionRefusedError)

    def test_dns_lookup_error(self):
        iterator = txhttpstream.getStreamedPagesIterator("http://jklasdfljkweljkewjklfljkwl")
        return self._consume_iterator(iterator).addCallback(self._verify_failures, error.DNSLookupError)

    def test_timeout(self):
        self.startTestServer([],1)
        iterator = txhttpstream.getStreamedPagesIterator("http://localhost:8080", timeout=0.01)
        return self._consume_iterator(iterator).addCallback(self._verify_failures, defer.TimeoutError)

    def test_splits_chunks(self):
        key = ["1","2"]
        def verify((results, failures)):
            results = filter(None, results)
            nt.assert_equal(failures,[])
            nt.assert_equal(set(results), set(key))

        all_in_one = "%s" % "\r\n".join(key)
        self.startTestServer([all_in_one],0, add_delim=False)
        iterator = txhttpstream.getStreamedPagesIterator("http://localhost:8080")
        return self._consume_iterator(iterator).addCallback(verify)

