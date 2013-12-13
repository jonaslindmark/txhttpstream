from twisted.web import server, resource
from twisted.internet import reactor

class StreamedHttpServer(resource.Resource):
    isLeaf = True

    def __init__(self, chunks_to_serve, delay_between_chunks=0, add_delim=True):
        self.add_delim = add_delim
        self.chunks_to_serve = chunks_to_serve
        self.delay_between_chunks = delay_between_chunks
        self.delayed_calls = []

    def render_GET(self, request):
        def render(request, chunks, delay):
            if chunks:
                data = chunks[0]
                if self.add_delim:
                    data = "%s\r\n" % data
                request.write(data)
                dl = reactor.callLater(delay, render, request, chunks[1:], delay)
                self.delayed_calls.append(dl)
            else:
                request.finish()

        dl = reactor.callLater(self.delay_between_chunks,
                render,
                request,
                self.chunks_to_serve,
                self.delay_between_chunks)
        self.delayed_calls.append(dl)
        return server.NOT_DONE_YET

    def stop(self):
        def stop_delayed_calls(ign):
            for delayed_call in filter(lambda dl: dl.active(), self.delayed_calls):
                delayed_call.cancel()
        return self.port.stopListening().addCallback(stop_delayed_calls)

    @classmethod
    def start(cls, port, chunks, delay, add_delim=True):
        resource = StreamedHttpServer(chunks, delay, add_delim=add_delim)
        site = server.Site(resource)
        resource.port = reactor.listenTCP(port, site)
        return resource


def startTestServer(port, chunks, delay, add_delim=True):
    return StreamedHttpServer.start(port, chunks, delay, add_delim=add_delim)
