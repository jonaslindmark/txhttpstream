from twisted.web import client
from twisted.internet import reactor, defer
from urlparse import urlparse
from collections import deque


class StreamFinished(Exception):
    pass


class StreamedHTTPGetter(client.HTTPPageGetter):
    def __init__(self, delimiter='\r\n'):
        self._intercept = False
        self._delimiter = delimiter
        self._read_index = 0
        self._chunks = deque()
        self._streamed_buffer = ""
        self._finished = False
        self._chunkReadyDeferred = defer.Deferred()

    def _handleData(self, data):
        chunks = data.split(self._delimiter)
        chunks[0] = self._streamed_buffer + chunks[0]
        self._streamed_buffer = ""
        if data.endswith(self._delimiter):
            self._chunks.extend(chunks[:-1])
        else:
            self._streamed_buffer = chunks[len(chunks)-1]
            self._chunks.extend(chunks[:-1])

        d, self._chunkReadyDeferred =  self._chunkReadyDeferred, defer.Deferred()
        d.callback(None)

    def rawDataReceived(self, data):
        client.HTTPPageGetter.rawDataReceived(self, data)
        self._handleData(data)

    def handleResponseEnd(self):
        if len(self._streamed_buffer) > 0:
            self._chunks.append(self._streamed_buffer)
            self._streamed_buffer = ""
            d, self._chunkReadyDeferred =  self._chunkReadyDeferred, defer.Deferred()
            d.callback(self._streamed_buffer)
        client.HTTPPageGetter.handleResponseEnd(self)
        self._finished = True
        self._chunkReadyDeferred.callback(None)

    def _getNextChunkByIndex(self, index):
        if len(self._chunks) == 0:
            if self._finished:
                return defer.fail(StreamFinished())
            return self._chunkReadyDeferred.addCallback(lambda ign: self._getNextChunkByIndex(index))
        else:
            chunk = self._chunks.popleft()
            return defer.succeed(chunk)

    def getNextChunk(self):
        d = self._getNextChunkByIndex(self._read_index)
        self._read_index = self._read_index + 1
        return d

    def factoryErrback(self, failure):
        self._chunkReadyDeferred.errback(failure)
        return failure


def resultStream(streamedHttpGetter):
    def checkDone(f):
        f.trap(StreamFinished)

    def recur(chunk):
        d = resultStream(streamedHttpGetter)
        return (chunk, d)

    return streamedHttpGetter.getNextChunk() \
            .addCallbacks(recur, checkDone)


class ResultStreamIterator(object):
    def __init__(self, protocolDeferred):
        self.protocolDeferred = protocolDeferred
        self.protocolDeferred.addCallbacks(self._setupProtocol, self.handleError)
        self._empty = False
        self.protocol = None
        self._failure = None

    def handleError(self, f):
        self._failure = f
        self._empty = True

    def _setupProtocol(self, protocol):
        self.protocol = protocol

    def __iter__(self):
        return self

    def _next(self):
        def handleErrors(f):
            if f.check(StreamFinished):
                self._empty = True
            else:
                self._failure = f
                self._empty = True
                return f

        if self._failure:
            return defer.fail(self._failure)

        if self._empty:
            return defer.succeed(None)

        return self.protocol.getNextChunk() \
                .addErrback(handleErrors)

    def next(self):
        if self._empty:
            raise StopIteration

        if self.protocol is not None:
            return self._next()

        return self.protocolDeferred.addCallback(lambda ign: self._next())


class HTTPClientFactoryWithProtocol(client.HTTPClientFactory):
    def __init__(self, *args, **kwargs):
        client.HTTPClientFactory.__init__(self, *args, **kwargs)
        self.protocolDeferred = defer.Deferred()
        self.streamedResult = None

    def buildProtocol(self, addr):
        p = client.HTTPClientFactory.buildProtocol(self, addr)
        self.protocolInstance = p
        self.protocolDeferred.callback(p)
        return p


def _getStreamedPages(url, *args, **kwargs):
    parsed_url = urlparse(url)
    factory = HTTPClientFactoryWithProtocol(url, *args, **kwargs)
    factory.protocol = StreamedHTTPGetter
    reactor.connectTCP(parsed_url.hostname, parsed_url.port, factory)

    def errback(f):
        if not factory.protocolDeferred.called:
            factory.protocolDeferred.errback(f)
        else:
            factory.protocolInstance.factoryErrback(f)

    factory.deferred.addErrback(errback)
    return factory.protocolDeferred


def getStreamedPages(url, *args, **kwargs):
    return _getStreamedPages(url, *args, **kwargs) \
            .addCallback(resultStream)


def getStreamedPagesIterator(url, *args, **kwargs):
    protocolDeferred = _getStreamedPages(url, *args, **kwargs)
    return ResultStreamIterator(protocolDeferred)

