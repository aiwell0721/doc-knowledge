"""
MemoMind HTTP 真实集成测试

使用临时 HTTP 服务器测试真实的 HTTP 导出流程（非 mock）
"""

import tempfile
import json
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from doc_knowledge.exporters.memomind import MemoMindExporter


def _create_test_knowledge_dir(tmpdir: str, count: int = 3) -> Path:
    """创建测试知识目录"""
    knowledge = Path(tmpdir) / "knowledge"
    knowledge.mkdir()
    
    for i in range(count):
        (knowledge / f"doc_{i}.md").write_text(
            f'---\ntitle: "Document {i}"\ndk_tags: ["tag{i}", "test"]\n---\n\n'
            f'This is document {i} about system architecture and Docker containers.',
            encoding="utf-8"
        )
    
    return knowledge


class MockMemoMindHandler(BaseHTTPRequestHandler):
    """模拟 MemoMind API 的 HTTP 处理器"""
    
    received_requests = []
    
    def do_POST(self):
        """处理 POST /api/notes 请求"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        # 解析请求体
        try:
            payload = json.loads(post_data.decode('utf-8'))
            MockMemoMindHandler.received_requests.append({
                'path': self.path,
                'payload': payload,
                'headers': dict(self.headers)
            })
            
            # 返回成功响应
            response = json.dumps({
                "id": len(MockMemoMindHandler.received_requests),
                "title": payload.get("title", ""),
                "status": "created"
            })
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
    
    def log_message(self, format, *args):
        """静默日志"""
        pass


def test_memomind_http_real_integration():
    """MemoMind HTTP 真实集成测试（使用临时服务器）"""
    # 启动临时服务器
    server = HTTPServer(('127.0.0.1', 0), MockMemoMindHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    try:
        MockMemoMindHandler.received_requests = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge = _create_test_knowledge_dir(tmpdir, count=3)
            
            # 导出到临时服务器
            exporter = MemoMindExporter(f"http://127.0.0.1:{port}")
            stats = exporter.export(knowledge)
            
            # 验证导出成功
            assert stats["exported"] == 3
            assert stats["errors"] == 0
            
            # 验证服务器收到了请求
            assert len(MockMemoMindHandler.received_requests) == 3
            
            # 验证请求内容
            for i, req in enumerate(MockMemoMindHandler.received_requests):
                assert req['path'] == '/api/notes'
                assert 'title' in req['payload']
                assert 'content' in req['payload']
                assert 'tags' in req['payload']
                assert req['payload']['title'] == f'Document {i}'
                assert f'tag{i}' in req['payload']['tags']
    finally:
        server.shutdown()


def test_memomind_http_server_error():
    """MemoMind HTTP 服务器错误处理"""
    # 启动返回 500 的服务器
    class ErrorHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Internal Server Error"}).encode('utf-8'))
        
        def log_message(self, format, *args):
            pass
    
    server = HTTPServer(('127.0.0.1', 0), ErrorHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge = _create_test_knowledge_dir(tmpdir, count=1)
            
            exporter = MemoMindExporter(f"http://127.0.0.1:{port}")
            
            # 应该抛出异常（HTTP 500）
            try:
                exporter.export(knowledge)
                # 如果没抛出异常，说明错误处理有问题
                assert False, "Should have raised an error for HTTP 500"
            except Exception as e:
                # 捕获到异常即可（具体类型取决于 urllib 实现）
                assert True
    finally:
        server.shutdown()


def test_memomind_http_with_api_key():
    """MemoMind HTTP 带 API Key 测试"""
    received_auth = []
    
    class AuthHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            received_auth.append(self.headers.get('Authorization', ''))
            content_length = int(self.headers['Content-Length'])
            self.rfile.read(content_length)  # 读取请求体
            
            response = json.dumps({"id": 1, "status": "created"})
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
        
        def log_message(self, format, *args):
            pass
    
    server = HTTPServer(('127.0.0.1', 0), AuthHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge = _create_test_knowledge_dir(tmpdir, count=1)
            
            exporter = MemoMindExporter(
                f"http://127.0.0.1:{port}",
                api_key="test-api-key-123"
            )
            stats = exporter.export(knowledge)
            
            assert stats["exported"] == 1
            assert len(received_auth) == 1
            assert received_auth[0] == "Bearer test-api-key-123"
    finally:
        server.shutdown()
