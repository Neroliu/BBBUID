# BBBUID

<p align="center">
  <a href="https://github.com/Genshin-bots/gsuid_core"><img src="https://uploadstatic.mihoyo.com/bh3-wiki/2022/12/01/264755623/12fb1d508d8e392c9b6ecd794a98274e_1660936160398365933.png" width="256" height="256" alt="BBBUID"></a>
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
| UID管理 | 绑定/切换/删除UID |
| WIKI查询 | 角色、武器、圣痕、人偶、协同者图鉴查询 |
| WIKI搜索 | 关键词搜索崩坏3百科内容 |
| 定时任务 | 每日凌晨2点自动签到（需开启订阅） |

## 丨命令列表

### 基础命令
| 命令 | 说明 |
|------|------|
| `bbb绑定uid <uid>` | 绑定崩坏3 UID |
| `bbb切换uid` | 切换已绑定的UID |
| `bbb删除uid <uid>` | 解绑UID |
| `bbb帮助` | 查看帮助信息 |

### 签到命令
| 命令 | 说明 |
|------|------|
| `bbb签到` | 手动执行米游社签到 |
| `bbb开启自动签到` | 开启每日自动签到 |
| `bbb关闭自动签到` | 关闭每日自动签到 |
| `bbb全部重签` | 管理员命令，重新执行所有签到 |

### WIKI查询命令
| 命令 | 说明 |
|------|------|
| `bbb角色图鉴 <名称>` | 查询女武神角色信息 |
| `bbb武器图鉴 <名称>` | 查询武器信息 |
| `bbb圣痕图鉴 <名称>` | 查询圣痕信息 |
| `bbb人偶图鉴 <名称>` | 查询人偶信息 |
| `bbb协同者图鉴 <名称>` | 查询协同者信息 |
| `bbbwiki <关键词>` | 搜索崩坏3百科 |

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

## 致谢

- [Wuyi 无疑](https://github.com/KimigaiiWuyi)
- [gsuid_core](https://github.com/Genshin-bots/gsuid_core)
- [米游社崩坏3百科](https://baike.mihoyo.com/bh3/wiki/)
