# Doc-Knowledge 故障排查

> 常见问题及解决方案。

---

## 安装问题

### Q: 安装后提示 `markitdown` 依赖缺失

**症状**：
```
FileConversionException: DocxConverter recognized the input as a potential .docx file, 
but the dependencies needed to read .docx files have not been installed.
```

**解决**：
```bash
# 安装完整版
pip install "markitdown[docx]"

# 或安装所有格式支持
pip install "markitdown[docx,pdf,pptx,xlsx]"
```

### Q: PDF 转换失败

**症状**：转换 PDF 时报错。

**解决**：
```bash
# 安装 PDF 依赖
pip install pdfplumber pdfminer.six
```

### Q: PPTX 转换失败

**症状**：转换 PPTX 时报错。

**解决**：
```bash
pip install python-pptx
```

---

## 转换问题

### Q: 转换后内容为空

**可能原因**：
1. 文件格式不支持
2. 文件已损坏
3. 文件是扫描件（需要 OCR）

**排查步骤**：
```bash
# 使用 verbose 模式查看详细信息
doc-knowledge convert ./docs -v

# 使用 dry-run 预览
doc-knowledge convert ./docs --dry-run
```

### Q: 部分文件转换失败

**症状**：转换报告中显示错误。

**解决**：
- 使用 `-v` 查看具体错误信息
- 损坏的文件会被跳过，不影响其他文件
- 如需转换扫描件，安装 OCR 支持：`pip install markitdown-ocr`

---

## 提取问题

### Q: 去重效果不理想

**解决**：
- 调整阈值：`--threshold 0.9`（更严格）或 `--threshold 0.7`（更宽松）
- 大规模文件使用 SimHash：`--simhash`

### Q: 版本合并没有生效

**原因**：文件名不符合版本模式。

**支持的版本模式**：
- `report_v1.md`, `report_v2.md`
- `doc.v1.md`, `doc.v2.md`
- `design_ver1.md`
- `report_20260517.md`
- `report_final.md`

---

## 导出问题

### Q: Obsidian 导出后看不到文件

**检查**：
1. Vault 路径是否正确
2. 导出目录是否有写权限

### Q: MemoMind 导出连接失败

**症状**：
```
无法连接 MemoMind API (http://localhost:8000): ...
```

**解决**：
1. 确认 MemoMind 服务正在运行
2. 检查 API 地址和端口是否正确
3. 使用本地 MCP 模式替代：`--db /path/to/memomind.db`

---

## 性能问题

### Q: 大量文件转换很慢

**优化建议**：
- 使用 `--format` 仅转换需要的格式
- 大规模去重使用 `--simhash`（O(n) 算法）
- 增量更新使用 `--incremental`（仅处理变更文件）

### Q: 内存占用过高

**解决**：
- 分批处理大目录
- 使用临时目录：`--temp-dir /path/to/tmp`

---

## 其他问题

### Q: 中文文件名显示乱码

**解决**：确保系统编码为 UTF-8。

### Q: Windows 下终端显示异常

**症状**：进度条或彩色输出显示异常。

**解决**：这是终端兼容性问题，不影响功能。使用 `--quiet` 可以禁用彩色输出。
