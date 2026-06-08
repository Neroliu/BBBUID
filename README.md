# BBBUID

<p align="center">
  <a href="https://github.com/Genshin-bots/gsuid_core"><img src="ICON.png" width="256" height="256" alt="BBBUID"></a>
</p>
<h1 align="center">BBBUID 1.0.0</h1>
<h4 align="center">支持OneBot(QQ)、QQ频道、微信、开黑啦、Telegram的崩坏3插件</h4>
<div align="center">
  <a href="https://docs.sayu-bot.com/" target="_blank">安装文档</a> &nbsp; · &nbsp;
  <a href="https://github.com/Genshin-bots/gsuid_core" target="_blank">gsuid_core</a>
</div>

## 丨功能一览

| 功能 | 说明 |
|------|------|
| 米游社签到 | 支持手动签到与每日自动签到（需绑定Cookie） |
| UID管理 | 绑定/切换/删除/查看UID |
| 数据查询 | 女武神、便笺、深渊、战场、往世乐土查询 |
| WIKI查询 | 角色、武器、圣痕、人偶、协同者图鉴查询 |
| WIKI搜索 | 关键词搜索崩坏3百科内容 |
| 别名管理 | 自定义角色别名 |
| 定时任务 | 每日凌晨2点自动签到（需开启订阅） |

## 丨命令列表

### 基础命令
| 命令 | 说明 |
|------|------|
| `bbb绑定uid <uid>` | 绑定崩坏3 UID |
| `bbb切换uid` | 切换已绑定的UID |
| `bbb删除uid <uid>` | 解绑UID |
| `bbb查看uid` | 查看已绑定的UID列表 |
| `bbb帮助` | 查看帮助信息 |

### 签到命令
| 命令 | 说明 |
|------|------|
| `bbb签到` | 手动执行米游社签到 |
| `bbb开启自动签到` | 开启每日自动签到 |
| `bbb关闭自动签到` | 关闭每日自动签到 |
| `bbb全部重签` | 管理员命令，重新执行所有签到 |

### 数据查询命令
| 命令 | 说明 |
|------|------|
| `bbb查询` | 查询女武神首页/概况 |
| `bbb便笺` | 查询实时便笺（体力/日程） |
| `bbb深渊` | 查询深渊/超弦空间战报 |
| `bbb战场` | 查询战场战报/记忆战场 |
| `bbb往世乐土` | 查询往世乐土记录 |
| `bbb刷新面板` | 刷新角色数据缓存 |

### WIKI查询命令
| 命令 | 说明 |
|------|------|
| `bbb角色图鉴 <名称>` | 查询女武神角色信息 |
| `bbb武器图鉴 <名称>` | 查询武器信息 |
| `bbb圣痕图鉴 <名称>` | 查询圣痕信息 |
| `bbb人偶图鉴 <名称>` | 查询人偶信息 |
| `bbb协同者图鉴 <名称>` | 查询协同者信息 |
| `bbbwiki <关键词>` | 搜索崩坏3百科 |

### 别名管理命令
| 命令 | 说明 |
|------|------|
| `bbb添加<角色>别名<别名>` | 为角色添加别名 |
| `bbb删除<角色>别名<别名>` | 删除角色的别名 |
| `bbb<角色>别名` | 查看角色的所有别名 |

## 丨安装提醒

> **注意：该插件为 [早柚核心(gsuid_core)](https://github.com/Genshin-bots/gsuid_core) 的扩展，具体安装方式可参考上方安装文档**
>
> **运行环境要求 Python `3.11+`**
>
> **如果已经是最新版本的 `gsuid_core`，可以直接对 bot 发送 `core安装插件BBBUID`，然后重启 Core 以应用安装**
>
> 签到功能需要绑定米游社Cookie，请确保已正确绑定
>
> 🚧 插件仍在持续完善中 🚧

### 可选：启用 HTML 渲染（实验性）

插件默认使用 PIL 渲染图片。若想体验更精致的 HTML + CSS 渲染（基于 Playwright），按以下步骤启用：

1. 安装依赖：`pip install playwright jinja2 && playwright install chromium`
2. 在 webconsole 中将 `HTML 渲染（实验性）` 开关打开
3. 已迁移到 HTML 的指令：`bbbmr`（便笺）。其余指令仍走 PIL 渲染

## 丨WIKI数据来源

WIKI查询功能使用米游社崩坏3百科API：
- 女武神：109个角色
- 武器：386个武器
- 圣痕：689个圣痕
- 人偶：13个人偶
- 协同者：7个协同者

数据实时同步自 [崩坏3百科](https://baike.mihoyo.com/bh3/wiki/)

## 丨其他

- 本项目仅供学习使用，请勿用于商业用途
- [GPL-3.0 License](LICENSE)

## 丨使用限制

> [!CAUTION]
> 本项目内的所有模板文件，以及任何用于 UI 渲染的相关资源，**未经原作者书面授权，不得以任何形式拷贝、二次修改或重新发布**。该限制涵盖但不局限于以下场景：
>
> - 上传至公开仓库或个人网站托管
> - 转载、二次散布或在社群中分享原始 / 修改版文件
> - 打包或内嵌进其他插件、应用、项目使用
>
> 如需取得授权，请联系 [Wuyi 无疑](https://github.com/KimigaiiWuyi)。

## 致谢

- [Wuyi 无疑](https://github.com/KimigaiiWuyi)
- [gsuid_core](https://github.com/Genshin-bots/gsuid_core)
- [米游社崩坏3百科](https://baike.mihoyo.com/bh3/wiki/)
