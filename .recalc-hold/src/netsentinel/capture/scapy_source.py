"""Socket passivo persistente: não transmite nem executa mitigação."""
from scapy.all import conf, get_if_list, sniff


class ScapySource:
    def __init__(self, interface):
        self.interface = interface
        self.socket = None

    def __enter__(self):
        if self.interface not in get_if_list():
            raise ValueError(f"Interface inexistente: {self.interface}")
        self.socket = conf.L2listen(iface=self.interface, promisc=True)
        return self

    def poll(self, callback):
        # Reutilizar o socket evita reabri-lo entre publicações, inclusive no silêncio.
        sniff(opened_socket=self.socket, promisc=True, store=False,
              prn=callback, timeout=1, chainCC=True)

    def __exit__(self, *_):
        if self.socket is not None:
            self.socket.close()
            self.socket = None
