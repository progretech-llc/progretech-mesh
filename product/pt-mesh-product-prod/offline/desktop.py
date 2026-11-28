"""Native desktop launcher and bundled factory worker entry point."""
import os
import json
import sys
import threading
from pathlib import Path


def resource_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def prepare_environment():
    root = resource_root()
    node = root / 'runtimes/node' / ('node.exe' if os.name == 'nt' else 'bin/node')
    git = root / 'runtimes/git'
    if node.is_file(): os.environ['MESH_OFFICE_NODE'] = str(node)
    paths = [str(git / 'cmd'), str(git / 'bin'), str(node.parent)]
    os.environ['PATH'] = os.pathsep.join(paths + [os.environ.get('PATH', '')])
    if (git / 'libexec/git-core').is_dir(): os.environ['GIT_EXEC_PATH'] = str(git / 'libexec/git-core')
    os.environ['CREWAI_TELEMETRY_DISABLED'] = 'true'
    os.environ['OTEL_SDK_DISABLED'] = 'true'
    os.environ['DO_NOT_TRACK'] = '1'


def main():
    prepare_environment()
    if len(sys.argv) > 1 and sys.argv[1] == '--factory-worker':
        sys.argv.pop(1)
        from control_center.factory_worker import main as worker
        return worker()
    if '--self-test' in sys.argv:
        import tempfile
        from control_center.office import engine
        from offline.app import create_app
        with tempfile.TemporaryDirectory() as home:
            state = engine(home, 'offline', 'snapshot')['snapshot']
            assert state['agents'][0]['isDirector']
            import crewai, llama_cpp
            model = resource_root() / 'runtimes/models/starter.gguf'
            if model.is_file():
                runtime = llama_cpp.Llama(model_path=str(model), n_ctx=512, verbose=False)
                answer = runtime.create_chat_completion(messages=[{'role':'user','content':'Say hello.'}], max_tokens=8)
                assert answer['choices'][0]['message']['content']
            app = create_app(home, 'test-local-cookie')
            client = app.test_client()
            client.set_cookie('mesh_local', 'test-local-cookie', domain='127.0.0.1')
            assert client.get('/', base_url='http://127.0.0.1').status_code == 200
        print('Mesh Offline self-test passed: local UI, bundled inference, CrewAI and Hive coordination')
        return
    from PySide6.QtCore import QUrl, QByteArray, QStandardPaths, QTimer
    from PySide6.QtNetwork import QNetworkCookie
    if os.name == 'nt':
        import ctypes
        console = ctypes.windll.kernel32.GetConsoleWindow()
        if console: ctypes.windll.user32.ShowWindow(console, 0)
    from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QFileDialog
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineUrlRequestInterceptor
    from werkzeug.serving import make_server
    from offline.app import create_app
    qt = QApplication(sys.argv)
    qt.setApplicationName('Mesh Offline'); qt.setOrganizationName('ProgreTech')
    home = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
    smoke = '--desktop-smoke' in sys.argv
    if smoke:
        import tempfile
        temporary = tempfile.TemporaryDirectory()
        home = Path(temporary.name)
    home.mkdir(parents=True, exist_ok=True)
    app = create_app(home)
    # Track WSGI work explicitly: GUI shutdown must not remove workspaces while
    # an accepted request is still launching or waiting for a native child.
    requests = threading.Condition()
    active = [0]
    original_wsgi = app.wsgi_app
    def tracked_wsgi(environ, start_response):
        with requests: active[0] += 1
        try:
            response = original_wsgi(environ, start_response)
            yield from response
        finally:
            if 'response' in locals() and hasattr(response, 'close'): response.close()
            with requests:
                active[0] -= 1
                requests.notify_all()
    app.wsgi_app = tracked_wsgi
    try:
        server = make_server('127.0.0.1', 0, app, threaded=True)
        # Drain active local requests before releasing their workspaces. A
        # Windows child process can keep its current directory open until exit.
        server.daemon_threads = False
    except OSError as exc:
        QMessageBox.critical(None, 'Mesh Offline', 'The local engine could not start: ' + str(exc)); return 1
    origin = 'http://127.0.0.1:' + str(server.server_port)
    class LocalRequests(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, info):
            url = info.requestUrl()
            if url.scheme() not in {'data', 'blob'} and not (url.scheme() == 'http' and url.host() == '127.0.0.1' and url.port() == server.server_port):
                info.block(True)
    view = QWebEngineView()
    # Off-the-record profile: no remembered cloud login, service worker or disk cookie.
    profile = QWebEngineProfile(view)
    interceptor = LocalRequests(profile); profile.setUrlRequestInterceptor(interceptor)
    from PySide6.QtWebEngineCore import QWebEnginePage
    view.setPage(QWebEnginePage(profile, view))
    cookie = QNetworkCookie(QByteArray(b'mesh_local'), QByteArray(app.config['LOCAL_TOKEN'].encode()))
    cookie.setPath('/'); cookie.setHttpOnly(True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    window = QMainWindow(); window.setWindowTitle('Mesh Offline · ProgreTech')
    window.resize(1320, 860); window.setCentralWidget(view)
    menu = window.menuBar().addMenu('Files')
    def choose(kind):
        if kind == 'workspace': path = QFileDialog.getExistingDirectory(window, 'Agent workspace')
        else:
            path, _ = QFileDialog.getOpenFileName(window, 'Choose ' + kind, '', 'GGUF models (*.gguf)' if kind == 'model' else 'Python (*.py)' if kind == 'entrypoint' else 'All files (*)')
        if not path: return
        field = 'gguf' if kind == 'model' else kind
        target = 'modelForm' if kind == 'model' else 'localImport'
        view.page().runJavaScript(f"const f=document.getElementById({json.dumps(target)}); if(f){{f.elements[{json.dumps(field)}].value={json.dumps(path)};}}")
    for label, kind in [('Choose local model…','model'), ('Choose agent workspace…','workspace'), ('Choose runtime executable…','executable'), ('Choose Python entry point…','entrypoint')]:
        action = menu.addAction(label); action.triggered.connect(lambda checked=False, value=kind: choose(value))
    # Start navigation only after Qt has installed the private desktop cookie.
    loaded = [False]
    def cookie_ready(added):
        if bytes(added.name()) == b'mesh_local' and not loaded[0]:
            loaded[0] = True; view.setUrl(QUrl(origin))
    profile.cookieStore().cookieAdded.connect(cookie_ready)
    profile.cookieStore().setCookie(cookie, QUrl(origin))
    window.show()
    if smoke:
        def verify(loaded):
            if not loaded:
                print('Desktop load failed', file=sys.stderr); qt.exit(1); return
            def checked(title):
                if title != 'Mission Control':
                    print('Desktop cookie or rendering failed: ' + str(title), file=sys.stderr); qt.exit(1); return
                if os.environ.get('MESH_SMOKE_SCREENSHOT'): window.grab().save(os.environ['MESH_SMOKE_SCREENSHOT'])
                print('Mesh Offline native desktop smoke passed'); qt.exit(0)
            QTimer.singleShot(500, lambda: view.page().runJavaScript("document.querySelector('h1')?.textContent", checked))
        view.loadFinished.connect(verify)
        QTimer.singleShot(30000, lambda: qt.exit(2))
    result = qt.exec()
    server.shutdown(); server.server_close()
    with requests: requests.wait_for(lambda: active[0] == 0)
    # The page must release Chromium resources before its off-record profile.
    from shiboken6 import delete
    delete(view.page()); delete(profile); delete(window)
    if smoke: temporary.cleanup()
    return result


if __name__ == '__main__': raise SystemExit(main())
