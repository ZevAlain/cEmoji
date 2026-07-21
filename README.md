![cEmoji](https://raw.githubusercontent.com/ZevAlain/cEmoji/main/my_icon.ico)

# cEmoji

[![](https://img.shields.io/github/release/ZevAlain/cEmoji.svg)](https://github.com/ZevAlain/cEmoji/releases/latest)
[![LICENSE](https://img.shields.io/github/license/ZevAlain/cEmoji "LICENSE")](./LICENSE "LICENSE")

cEmoji 是一个 Windows 表情包剪贴板工具。它可以导入图片或 ZIP 表情包，按本地合集管理表情，搜索、置顶并把选中的图片复制到剪贴板，方便在聊天、会议、文档等场景中快速使用。

## 功能

- [x] 导入 PNG、JPG、JPEG、GIF 表情包图片
- [x] 导入 ZIP 格式表情包，支持 ZIP 内嵌套目录
- [x] 图片、ZIP、剪贴板导入结果统计，显示成功、跳过和失败数量
- [x] 内容去重，同图不同名不会重复导入
- [x] 点击表情复制到剪贴板，GIF 复制保留动图支持
- [x] 搜索本地表情包
- [x] 本地多合集管理，单个表情文件可加入多个合集但只保存一份
- [x] 紧凑主界面布局，合集、搜索、分类和常用操作集中在顶部两行
- [x] 长合集名悬停滚动显示，支持本地合集和云端合集列表
- [x] 右键置顶表情包，置顶状态持久保存
- [x] GIF 表情角标提示，鼠标悬停 1 秒可预览播放
- [x] 云端表情包库，支持搜索、分类预览、按图或按合集下载到本地表情库
- [x] 云端预览缓存和安全校验，减少重复下载并过滤非白名单图片格式
- [x] 管理模式下删除单个表情包
- [x] 按当前合集或全部表情包导出、清空
- [x] 当前窗口始终置顶
- [x] Windows 现代窗口效果，支持系统标题栏配色、圆角和可用时的 Mica 背景
- [x] 关闭或最小化隐藏到托盘，托盘菜单支持显示界面和退出
- [x] 全局快捷键呼出或隐藏主界面
- [x] 单实例运行，重复启动会唤起已有窗口

## 使用

1. 从 [Releases](https://github.com/ZevAlain/cEmoji/releases/latest) 下载最新版。
2. 解压后双击外层 `cEmoji.exe` 启动。
3. 点击“上传”，选择图片、ZIP 压缩包，或读取剪贴板图片。
4. 左键点击表情即可复制到剪贴板，在目标应用中粘贴使用。
5. 使用顶部合集入口切换本地合集，合集较多时可从“更多”中选择；长合集名悬停可滚动查看完整名称。
6. 右键表情可置顶、从当前合集移除或删除本地文件，点击“管理”可快速从当前合集移除。
7. “更多”菜单可选择导出/清空当前合集，或导出/清空所有表情包。
8. 在“更多”菜单中打开“云端表情包库”，可搜索和下载云端表情。
9. 云端单张/多选下载可选择目标本地合集，按云端合集导入时默认创建同名本地合集。
10. 点击窗口关闭按钮会隐藏到托盘，如需退出请使用托盘菜单。

## 截图导入

读取剪贴板功能可以配合截图工具使用。

1. 使用 Snipaste、Windows 截图工具或其他工具截图。
2. 确认截图图片已经进入剪贴板。
3. 在 cEmoji 中点击“上传” -> “读取剪切板内容”。
4. 图片会保存到本地表情库。

Snipaste 下载地址：<https://www.snipaste.com/download.html>

## 已知问题

暂无已确认的高优先级问题。

## 官网文档

项目官网位于 [docs](docs) 目录，使用 VitePress 构建。

```bash
cd docs
npm install
npm run docs:dev
```

## License

GNU General Public License v3.0，详见 [LICENSE](LICENSE)。
