"""The central server: one Flask app owning accounts, dispatch and balances.

Kept free of import side effects so tests can import submodules directly;
the app factory lives in central_server.app.
"""
