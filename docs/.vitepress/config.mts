import { defineConfig } from 'vitepress';

// https://vitepress.dev/reference/site-config
export default defineConfig({
  lang: 'zh-CN',
  title: 'cEmoji',
  description: '表情包外挂 - Python 表情包扩展工具',
  cleanUrls: true,
  head: [
    ['link', { rel: 'icon', href: '/favicon.ico' }],
    ['meta', { name: 'theme-color', content: '#3c3c3d' }]
  ],
  sitemap: {
    hostname: 'https://zevalain.github.io/cEmoji',
  },
  
  themeConfig: {
    logo: '/logo.svg',
    logoLink: '/',
    
    siteTitle: 'cEmoji',

    nav: [
      { text: '首页', link: '/' },
      { text: '指南', link: '/guide/' },
      { text: 'GitHub', link: 'https://github.com/ZevAlain/cEmoji' }
    ],

    sidebar: {
      '/guide/': [
        {
          text: '开始使用',
          items: [
            { text: '什么是 cEmoji?', link: '/guide/' },
            { text: '快速开始', link: '/guide/快速开始' },
            { text: '安装指南', link: '/guide/安装指南' },
          ]
        },
        {
          text: '功能介绍',
          items: [
            { text: '功能列表', link: '/guide/功能说明' },
            { text: '使用教程', link: '/guide/使用教程' },
          ]
        },
        {
          text: '其他',
          items: [
            { text: '常见问题', link: '/guide/常见问题' },
            { text: '许可证', link: '/guide/许可证' },
          ]
        }
      ]
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/ZevAlain/cEmoji' }
    ],

    footer: {
      message: 'Released under the GPL-3.0 License.',
      copyright: 'Copyright © 2023-2026 ZevAlain'
    },

    editLink: {
      pattern: 'https://github.com/ZevAlain/cEmoji/edit/feat/vitepress-docs/docs/:path',
      text: '在 GitHub 编辑此页面'
    }
  }
});