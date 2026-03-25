# Markdown 文档分片和向量检索工具

基于 OpenAI Embeddings API 的 Markdown 文档智能分片和语义搜索工具。

## 功能

- 智能分片：按标题、段落结构分割 Markdown 文档
- 向量化：调用 OpenAI API 生成文本向量
- 语义搜索：基于余弦相似度的文档检索

## 安装

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="your-api-key"
```

## 使用

### 1. 分片并向量化文档

```bash
python3 split.py split README.md --output vectors.json
```

参数：
- `--chunk-size`: 分片大小（默认 1000）
- `--overlap`: 重叠字符数（默认 100）
- `--no-embeddings`: 仅分片不向量化
- `--model`: 嵌入模型（默认 text-embedding-3-small）

### 2. 查询相似文档

```bash
python3 split.py query "如何使用这个工具" --vector-store vectors.json --top-k 3
```

参数：
- `--vector-store, -v`: 向量存储文件路径（必需）
- `--top-k`: 返回结果数量（默认 5）

## 示例

```bash
# 处理文档
python3 split.py split awesome-cpp/README.md -o cpp_vectors.json

# 搜索相关内容
python3 split.py query "memory management" -v cpp_vectors.json --top-k 5
```

## Python API

```python
from split import MarkdownProcessor

# 分片和向量化
processor = MarkdownProcessor(chunk_size=1500, overlap=150)
chunks = processor.process_file('README.md')
processor.save_chunks(chunks, 'vectors.json')

# 查询
results = processor.query("search query", "vectors.json", top_k=5)
for result in results:
    print(f"Similarity: {result['similarity']:.4f}")
    print(f"Content: {result['chunk']['content'][:100]}...")
```
