from typing import Optional

from squirrel.client import Client

from .window import OpenPageSlot, get_window


class WindowLinker:
    """
    Mixin class that provides access methods for resources held by the main Window.
    These include:
    - client: first attempts to grab the client set at init, if none exists use the Window's client
    - open_page_slot: grabs the slot from the Window
    """

    def __init__(self, *args, client: Optional[Client] = None, **kwargs) -> None:
        self._client = client
        super().__init__(*args, **kwargs)

    @property
    def client(self) -> Optional[Client]:
        # Return the provided client if it exists, grab the Window's otherwise
        if self._client is not None:
            return self._client
        else:
            window = get_window()
            if window is not None:
                return window.client

    @client.setter
    def client(self, client: Client):
        if not isinstance(client, Client):
            raise TypeError(f"Cannot set a {type(client)} as a client")

        if client is self._client:
            return

        self._client = client

    @property
    def open_page_slot(self) -> Optional[OpenPageSlot]:
        window = get_window()
        if window is not None:
            return window.open_page

    def get_window(self):
        """Return the singleton Window instance"""
        return get_window()

    def refresh_window(self):
        """Refresh window ui elements"""
        # tree view
        window = get_window()
        window.tree_view.set_data(self.client.backend.root)
        window.tree_view.model().refresh_tree()
