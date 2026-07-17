# scripts

## generate_cloud_index.py

生成官网使用的云端表情包索引：

```powershell
python scripts\generate_cloud_index.py
```

脚本会读取 `scripts/cloud_index_excludes.json`，跳过不需要展示的一级目录。

## cloud_index_excludes.json

用于配置不展示在云端表情包库中的合集目录：

```json
{
  "excluded_package_paths": [
    "picture",
    "QQ"
  ]
}
```

这里填写的是 EmojiPackage 仓库中的一级目录名。
