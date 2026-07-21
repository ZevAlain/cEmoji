---
layout: home

hero:
  name: 'cEmoji'
  text: 'Windows 表情包剪贴板工具'
  tagline: 导入、搜索、复制、本地管理和云端下载表情包的轻量工具
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
    title: '紧凑浏览'
    details: '合集、搜索、分类和常用操作集中在顶部两行，支持长合集名悬停滚动显示'
  - icon: ☁️
    title: '云端表情库'
    details: '可搜索和预览云端表情包，支持单张、多选或按合集下载到本地表情库'
  - icon: 📌
    title: '置顶和现代窗口'
    details: '窗口可始终置顶，支持全局快捷键呼出，并在 Windows 上启用标题栏配色、圆角和可用时的 Mica 效果'
  - icon: 📂
    title: '本地管理'
    details: '支持本地多合集、搜索、排序、置顶、移除或删除，并可按当前合集或全部导出和清空'
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
- 通过“表情包 / GIF”切换静态表情和动态表情。
- 通过紧凑顶部栏切换本地合集、搜索、分类和排序。
- 在云端表情包库中搜索、预览并下载表情。
- 搜索、排序、置顶、按合集移除、删除、导出和清空本地表情。
- 支持全局快捷键呼出或隐藏主界面。
- 支持复制后自动隐藏到系统托盘。

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
