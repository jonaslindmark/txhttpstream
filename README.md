txhttpstream
============

Twisted Python HTTP client with incremental reading of data

Reasoning
============

When consuming large http responses that are sent with Transfer-Encoding: chunked it makes sense being able to perform operations on the intermediate results.

Usage
============
```python

    def handleChunk(result):
        if result is None:
            return
        (chunk, nextChunkDeferred) = result
        return performWork(chunk) \
                .addCallback(lambda ign: nextChunkDeferred.addCallback(handleChunk))

    return txhttpstream.getStreamedPages("http://stream.com/big-result") \
            .addCallback(handleChunk)
```

Or via iterator and the `twisted.task.coiterate` pattern

```python

    iterator = txhttpstream.getStreamedPagesIterator("http://stream.com/big-result")    
    work = imap(performWork, iterator)
    ds = [task.coiterate(work) for i in range(10)]
    return defer.gatherResults(ds)

```

Development
============

To test run `trial tests`
