# Doc-Knowledge Makefile
# 测试命令别名

.PHONY: test test-all test-cov test-html

# 运行测试（详细输出）
test:
	python -m pytest tests/ -v --tb=short

# 运行测试 + 覆盖率
test-all:
	python -m pytest tests/ -v --cov=src/doc_knowledge --cov-report=term-missing

# 生成 HTML 覆盖率报告
test-cov:
	python -m pytest tests/ --cov=src/doc_knowledge --cov-report=html
	@echo "覆盖率报告已生成：htmlcov/index.html"

# 打开 HTML 覆盖率报告
test-html: test-cov
	@echo "正在打开覆盖率报告..."
	@if [ -f "htmlcov/index.html" ]; then \
		start htmlcov/index.html; \
	else \
		echo "错误：未找到覆盖率报告"; \
	fi

# 运行单个测试文件
test-file:
	@if [ -z "$(FILE)" ]; then \
		echo "用法：make test-file FILE=tests/test_converter.py"; \
	else \
		python -m pytest $(FILE) -v --tb=short; \
	fi

# 运行特定测试
test-func:
	@if [ -z "$(FUNC)" ]; then \
		echo "用法：make test-func FUNC=test_converter.py::test_supported_extensions"; \
	else \
		python -m pytest $(FUNC) -v --tb=short; \
	fi
