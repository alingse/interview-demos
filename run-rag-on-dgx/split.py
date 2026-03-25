#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown文档分片和向量化工具
功能：
1. 解析 Markdown 文件
2. 按照合理的策略进行分片（标题、段落、代码块等）
3. 调用 OpenAI embeddings API 进行向量化
"""

import os
import re
import time
from pathlib import Path
from typing import List, Dict
import argparse


class MarkdownSplitter:
    """Markdown文档分片器"""

    def __init__(self, chunk_size: int = 1000, overlap: int = 100):
        """
        初始化分片器

        Args:
            chunk_size: 最大分片大小（字符数）
            overlap: 分片之间的重叠字符数
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

    def parse_markdown(self, file_path: str) -> List[Dict]:
        """
        解析 Markdown 文件并返回结构化内容

        Args:
            file_path: Markdown 文件路径

        Returns:
            包含标题、段落、代码块等结构化信息的列表
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 按行分割
        lines = content.split('\n')

        chunks = []
        current_chunk = ""
        current_title = "Root"

        for line in lines:
            # 检测标题
            if line.startswith('#'):
                header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
                if header_match:
                    title = header_match.group(2)

                    # 保存当前分片
                    if current_chunk.strip():
                        chunks.append({
                            'title': current_title,
                            'content': current_chunk.strip(),
                            'type': 'section'
                        })

                    current_title = title
                    current_chunk = line + '\n'
                    continue

            # 检测代码块
            if line.strip().startswith('```'):
                if current_chunk.strip():
                    chunks.append({
                        'title': current_title,
                        'content': current_chunk.strip(),
                        'type': 'text'
                    })
                    current_chunk = ""

                # 处理代码块
                current_chunk = line + '\n'
                continue

            # 普通文本行
            current_chunk += line + '\n'

            # 如果当前分片超过阈值，创建新分片
            if len(current_chunk) >= self.chunk_size:
                chunks.append({
                    'title': current_title,
                    'content': current_chunk.strip(),
                    'type': 'text'
                })

                # 保留重叠部分
                if self.overlap > 0:
                    lines_list = current_chunk.split('\n')
                    overlap_lines = []
                    char_count = 0
                    for line in reversed(lines_list):
                        if char_count + len(line) > self.overlap:
                            break
                        overlap_lines.insert(0, line)
                        char_count += len(line) + 1
                    current_chunk = '\n'.join(overlap_lines) + '\n'
                else:
                    current_chunk = ""

        # 添加最后一个分片
        if current_chunk.strip():
            chunks.append({
                'title': current_title,
                'content': current_chunk.strip(),
                'type': 'text'
            })

        return chunks

    def split_by_paragraph(self, content: str) -> List[str]:
        """
        按段落分割文本

        Args:
            content: 文本内容

        Returns:
            段落列表
        """
        paragraphs = re.split(r'\n\s*\n', content.strip())
        return [p.strip() for p in paragraphs if p.strip()]

    def split_by_size(self, text: str) -> List[str]:
        """
        按固定大小分割文本（带重叠）

        Args:
            text: 输入文本

        Returns:
            分片后的文本列表
        """
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.overlap

        return chunks


class EmbeddingsClient:
    """OpenAI Embeddings API 客户端"""

    def __init__(self, api_key: str = None, base_url: str = "http://localhost:8010/v1"):
        """
        初始化客户端

        Args:
            api_key: OpenAI API 密钥（如未提供，将从环境变量读取）
            base_url: API 基础 URL（默认使用本地 vLLM 服务）
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY', 'dummy-key')
        self.base_url = base_url
        self.endpoint = f"{base_url}/embeddings"

    def create_embeddings(self, texts: List[str], model: str = "text-embedding-3-small") -> List[Dict]:
        """
        为文本列表创建向量嵌入

        Args:
            texts: 待嵌入的文本列表
            model: 使用的嵌入模型

        Returns:
            包含嵌入结果的字典列表
        """
        try:
            import requests
        except ImportError:
            raise ImportError("requests library is required. Install it with: pip install requests")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        results = []

        # API 限制单次请求的文本数量，需要分批处理
        batch_size = 100  # OpenAI 的限制

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            payload = {
                "input": batch,
                "model": model
            }

            try:
                response = requests.post(self.endpoint, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                for item in data['data']:
                    results.append({
                        'embedding': item['embedding'],
                        'index': item['index'],
                        'model': model
                    })

            except requests.exceptions.RequestException as e:
                print(f"Error creating embeddings for batch {i//batch_size}: {e}")
                # 为失败的批次添加占位符
                for _ in batch:
                    results.append({
                        'embedding': None,
                        'error': str(e),
                        'index': len(results)
                    })

        return results


class VectorStore:
    """向量存储和检索类"""

    def __init__(self):
        """初始化向量存储"""
        self.chunks = []
        self.embeddings = []

    def add_chunks(self, chunks: List[Dict]):
        """
        添加分片到向量存储

        Args:
            chunks: 包含 embedding 的分片列表
        """
        for chunk in chunks:
            if chunk.get('embedding'):
                self.chunks.append(chunk)
                self.embeddings.append(chunk['embedding'])

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        计算两个向量的余弦相似度

        Args:
            vec1: 向量1
            vec2: 向量2

        Returns:
            余弦相似度值 (0-1)
        """
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """
        根据查询向量搜索最相似的文档片段

        Args:
            query_embedding: 查询的向量表示
            top_k: 返回前 k 个最相似的结果

        Returns:
            相似度最高的文档片段列表
        """
        if not self.embeddings:
            return []

        # 计算所有文档的相似度
        similarities = []
        for i, doc_embedding in enumerate(self.embeddings):
            similarity = self.cosine_similarity(query_embedding, doc_embedding)
            similarities.append({
                'chunk': self.chunks[i],
                'similarity': similarity,
                'index': i
            })

        # 按相似度排序
        similarities.sort(key=lambda x: x['similarity'], reverse=True)

        # 返回前 k 个结果
        return similarities[:top_k]

    def save(self, file_path: str):
        """
        保存向量存储到文件

        Args:
            file_path: 保存路径
        """
        import json

        data = {
            'chunks': self.chunks,
            'total': len(self.chunks)
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Vector store saved to {file_path}")

    def load(self, file_path: str):
        """
        从文件加载向量存储

        Args:
            file_path: 文件路径
        """
        import json

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'chunks' in data:
            self.add_chunks(data['chunks'])
        else:
            # 兼容旧格式
            self.add_chunks(data.get('chunks', []))

        print(f"Loaded {len(self.chunks)} chunks from {file_path}")


class MarkdownProcessor:
    """Markdown 文档处理主类"""

    def __init__(self, chunk_size: int = 1000, overlap: int = 100):
        """
        初始化处理器

        Args:
            chunk_size: 最大分片大小
            overlap: 分片重叠大小
        """
        self.splitter = MarkdownSplitter(chunk_size, overlap)
        self.embeddings_client = None
        self.vector_store = VectorStore()

    def process_file(self, file_path: str, create_embeddings: bool = True) -> List[Dict]:
        """
        处理 Markdown 文件

        Args:
            file_path: Markdown 文件路径
            create_embeddings: 是否创建向量嵌入

        Returns:
            处理后的分片数据
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # 解析并分片
        chunks = self.splitter.parse_markdown(file_path)

        # 创建向量嵌入
        if create_embeddings:
            if self.embeddings_client is None:
                self.embeddings_client = EmbeddingsClient()

            texts = [chunk['content'] for chunk in chunks]
            embeddings = self.embeddings_client.create_embeddings(texts)

            # 将嵌入结果添加到分片中
            for i, embedding_data in enumerate(embeddings):
                if i < len(chunks):
                    chunks[i]['embedding'] = embedding_data.get('embedding')
                    chunks[i]['embedding_model'] = embedding_data.get('model')

        # 添加源文件信息
        for chunk in chunks:
            chunk['source_file'] = str(file_path)

        return chunks

    def save_chunks(self, chunks: List[Dict], output_path: str):
        """
        保存分片到文件

        Args:
            chunks: 分片数据
            output_path: 输出文件路径
        """
        try:
            import json
        except ImportError:
            raise ImportError("json library is required (built-in)")

        output_data = {
            'total_chunks': len(chunks),
            'chunks': chunks
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"Saved {len(chunks)} chunks to {output_path}")

    def query(self, query_text: str, vector_store_path: str, top_k: int = 5) -> List[Dict]:
        """
        根据查询文本搜索最相似的文档片段

        Args:
            query_text: 查询文本
            vector_store_path: 向量存储文件路径
            top_k: 返回前 k 个结果

        Returns:
            最相似的文档片段列表
        """
        # 加载向量存储
        self.vector_store.load(vector_store_path)

        # 创建查询的向量嵌入
        if self.embeddings_client is None:
            self.embeddings_client = EmbeddingsClient()

        query_embeddings = self.embeddings_client.create_embeddings([query_text])
        if not query_embeddings or not query_embeddings[0].get('embedding'):
            raise ValueError("Failed to create query embedding")

        query_embedding = query_embeddings[0]['embedding']

        # 搜索相似文档
        results = self.vector_store.search(query_embedding, top_k)

        return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Markdown文档分片和向量化工具')
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # split 命令
    split_parser = subparsers.add_parser('split', help='分片并向量化文档')
    split_parser.add_argument('file_path', help='Markdown文件路径')
    split_parser.add_argument('--output', '-o', help='输出文件路径（JSON格式）')
    split_parser.add_argument('--chunk-size', type=int, default=1000, help='最大分片大小（字符数）')
    split_parser.add_argument('--overlap', type=int, default=100, help='分片重叠字符数')
    split_parser.add_argument('--no-embeddings', action='store_true', help='不创建向量嵌入')
    split_parser.add_argument('--model', default='text-embedding-3-small', help='OpenAI嵌入模型')

    # query 命令
    query_parser = subparsers.add_parser('query', help='查询相似文档')
    query_parser.add_argument('query_text', help='查询文本')
    query_parser.add_argument('--vector-store', '-v', required=True, help='向量存储文件路径')
    query_parser.add_argument('--top-k', type=int, default=5, help='返回前 k 个结果')

    args = parser.parse_args()

    if args.command == 'split':
        # 创建处理器
        processor = MarkdownProcessor(chunk_size=args.chunk_size, overlap=args.overlap)

        # 处理文件
        print(f"Processing file: {args.file_path}")
        chunks = processor.process_file(args.file_path, create_embeddings=not args.no_embeddings)

        print(f"Created {len(chunks)} chunks")

        # 保存结果
        if args.output:
            processor.save_chunks(chunks, args.output)
        else:
            # 默认输出到同名 .json 文件
            output_path = Path(args.file_path).stem + '_chunks.json'
            processor.save_chunks(chunks, output_path)

        # 显示统计信息
        total_chars = sum(len(chunk['content']) for chunk in chunks)
        print(f"Total characters: {total_chars}")
        print(f"Average chunk size: {total_chars // len(chunks)}")

    elif args.command == 'query':
        # 创建处理器
        processor = MarkdownProcessor()

        # 执行查询
        print(f"Querying: {args.query_text}")
        results = processor.query(args.query_text, args.vector_store, args.top_k)

        # 显示结果
        print(f"\nFound {len(results)} results:\n")
        for i, result in enumerate(results, 1):
            chunk = result['chunk']
            similarity = result['similarity']
            print(f"Result {i} (Similarity: {similarity:.4f})")
            print(f"Title: {chunk.get('title', 'N/A')}")
            print(f"Source: {chunk.get('source_file', 'N/A')}")
            print(f"Content preview: {chunk['content'][:200]}...")
            print("-" * 80)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
