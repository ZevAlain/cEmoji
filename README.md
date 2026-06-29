![cEmoji](https://raw.githubusercontent.com/ZevAlain/cEmoji/main/my_icon.ico)

# cEmoji

[![](https://img.shields.io/github/release/ZevAlain/cEmoji.svg)](https://github.com/ZevAlain/cEmoji/releases/latest)
[![LICENSE](https://img.shields.io/github/license/ZevAlain/cEmoji "LICENSE")](./LICENSE "LICENSE")

cEmoji 是一个 Windows 表情包剪贴板工具。它可以导入图片或 ZIP 表情包，搜索、置顶、管理本地表情，并把选中的图片复制到剪贴板，方便在聊天、会议、文档等场景中快速使用。

## 功能

- [x] 导入 PNG、JPG、JPEG、GIF 表情包图片
- [x] 导入 ZIP 格式表情包，支持 ZIP 内嵌套目录
- [x] 图片、ZIP、剪贴板导入结果统计，显示成功、跳过和失败数量
- [x] 内容去重，同图不同名不会重复导入
- [x] 点击表情复制到剪贴板，GIF 复制保留动图支持
- [x] 搜索本地表情包
- [x] 右键置顶表情包，置顶状态持久保存
- [x] GIF 表情角标提示，鼠标悬停 1 秒可预览播放
- [x] 管理模式下删除单个表情包
- [x] 一键清空所有表情包
- [x] 当前窗口始终置顶，已修复切换置顶时闪烁的问题
- [x] 最小化隐藏到托盘，托盘菜单支持显示界面和退出
- [x] 全局快捷键呼出或隐藏主界面
- [x] 单实例运行，避免重复启动多个窗口

## 使用

1. 从 [Releases](https://github.com/ZevAlain/cEmoji/releases/latest) 下载最新版。
2. 解压后双击外层 `cEmoji.exe` 启动。
3. 点击“上传”，选择图片、ZIP 压缩包，或读取剪贴板图片。
4. 左键点击表情即可复制到剪贴板，在目标应用中粘贴使用。
5. 右键表情可置顶或删除，点击“管理”可进入快速删除模式。

## 截图导入

读取剪贴板功能可以配合截图工具使用。

1. 使用 Snipaste、Windows 截图工具或其他工具截图。
2. 确认截图图片已经进入剪贴板。
3. 在 cEmoji 中点击“上传” -> “读取剪切板内容”。
4. 图片会保存到本地表情库。

Snipaste 下载地址：<https://www.snipaste.com/download.html>

## 已知问题

暂无已确认的高优先级问题。旧版“点击始终置顶按钮会闪屏”的问题已经修复。

## 官网文档

项目官网位于 [docs](docs) 目录，使用 VitePress 构建。

```bash
cd docs
npm install
npm run docs:dev
```

## License

GNU General Public License v3.0，详见 [LICENSE](LICENSE)。
