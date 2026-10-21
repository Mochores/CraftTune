# CraftTune-V1.0.0

**CraftTune 的第一个大版本** · 2026-10-21

CraftTune-V1.0.0 是面向 Minecraft Java 版整合包的本地原生配置管理器。它把散落在 `config/` 里的 TOML、JSON5、YAML、Properties 和 CFG 文件整理成可搜索、可筛选、可撤销的图形化参数面板。

## 本版亮点

- **原生桌面界面**：PyQt5 窗口，不依赖浏览器，不启动本地 Web 服务。
- **版本与模组发现**：自动扫描 `.minecraft/versions`，识别 Fabric / Forge / NeoForge / Quilt / OptiFine。
- **配置自动关联**：按模组 ID、JAR 文件名和配置目录，把配置文件归到对应模组。
- **可视化参数编辑**：开关、数字、文本、枚举、数组和对象分别使用合适控件。
- **注释与格式保留**：保存时只替换目标值，不重排整个文件。
- **安全备份**：每次保存前备份原文件到 `data/backups`。
- **源码模式**：支持直接编辑原始文件；大文件自动切换，避免卡顿。
- **冲突保护**：文件被外部修改时拒绝覆盖。
- **直接启动 Minecraft**：左下角“启动游戏”由 CraftTune 自己生成 Java 命令，不经过 PCL/HMCL，自动处理 Java 运行时、natives、Fabric 加载器和缺失的客户端 JAR。
- **中文安装包**：按用户安装，无需管理员权限，带开始菜单/桌面快捷方式和卸载器。

## 安装

运行 `CraftTune-V1.0.0-Setup.exe`。默认安装到 `%LOCALAPPDATA%\Programs\CraftTune`。

## 已知限制

- 安装包未购买代码签名证书，Windows SmartScreen 可能提示未知发布者。
- 本机账号令牌过期时，直接启动会使用离线账号；单人游戏正常，正版服务器联机需先让启动器重新登录。
- 缺少版本清单的整合包无法直接启动。
- 卸载默认保留 `data/` 中的设置与备份。

## 技术栈

PyQt5 5.15 · minecraft-launcher-lib · Python 3.8 · Inno Setup 6
