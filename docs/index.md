---
layout: home

hero:
  name: 'cEmoji'
  text: 'Windows 表情包剪贴板工具'
  tagline: 导入、搜索、置顶、复制和管理本地表情包的轻量工具
  image:
    src: /logo.webp
    alt: cEmoji
  actions:
    - theme: brand
      text: '快速开始'
      link: /guide/快速开始
    - theme: alt
      text: '查看文档'
      link: /guide/
    - theme: alt
      text: 'GitHub'
      link: https://github.com/ZevAlain/cEmoji

features:
  - icon: 📦
    title: '批量导入'
    details: '支持 PNG、JPG、JPEG、GIF 图片和 ZIP 表情包，导入完成后显示成功、跳过和失败数量'
  - icon: 🧭
    title: '分类浏览'
    details: '支持在表情包和动态表情包之间切换，静态图片与 GIF 不再默认混在一起'
  - icon: 📌
    title: '置顶和快捷呼出'
    details: '窗口可始终置顶，支持全局快捷键呼出或隐藏主界面，置顶切换闪烁问题已修复'
  - icon: 📂
    title: '本地管理'
    details: '支持搜索、右键置顶、单个删除和一键清空所有表情包'
  - icon: 🖼️
    title: 'GIF 友好'
    details: 'GIF 表情可复制动图，列表显示 GIF 角标，悬停一秒可预览播放'
  - icon: 🚀
    title: '性能优化'
    details: '基于 PySide6 模型视图列表、缩略图缓存、后台导入和内容去重，减少卡顿和重复表情'
  - icon: 📝
    title: '开源项目'
    details: 'GNU General Public License v3.0 许可证，代码完全开源'
---

## 🎯 主要功能

- 导入图片、ZIP 和剪贴板图片。
- 点击表情复制到剪贴板，GIF 保留动图。
- 通过标签切换表情包和动态表情包。
- 搜索、置顶、删除和清空本地表情。
- 支持全局快捷键呼出或隐藏主界面。
- 支持复制后自动隐藏到系统托盘。
- “始终置顶”切换闪烁问题已经修复。

## 💡 快速了解

```bash
# 克隆项目
git clone https://github.com/ZevAlain/cEmoji.git

# 进入项目目录
cd cEmoji

# 运行源码版本
pip install -r requirements.txt
python cEmoji.py
```

## 🔧 工具要求

截图导入只要求剪贴板里有图片。可以使用 [Snipaste](https://www.snipaste.com/) 或 Windows 自带截图工具。

## 📞 获取帮助

遇到问题请到 [GitHub Issues](https://github.com/ZevAlain/cEmoji/issues) 反馈。

## 📄 许可证

GNU General Public License v3.0 - 详见 [LICENSE](https://github.com/ZevAlain/cEmoji/blob/main/LICENSE)
