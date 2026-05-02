# FitnessTrackerAndroid

原生 Android 版健身趋势记录器。这个项目不是 WebView 包壳；它直接读取内置 SQLite 数据库 `app/src/main/assets/workout.db`，在手机本地离线运行。

## 当前功能

- 查看历史训练总览：总组数、总训练量、训练天数、最高估算 1RM。
- 按月显示训练量趋势。
- 显示身体部位训练量分布。
- 显示最近训练记录。
- 每组训练后直接新增记录，默认使用当前时间。
- 动作名规范化逻辑与桌面版保持一致。

## 构建

本机已按当前脚本约定使用 `D:\Android` 下的 JDK 17、Android SDK 和 Gradle 8.10.2。

然后运行：

```powershell
.\build-apk.ps1
```

输出位置：

```text
app/build/outputs/apk/debug/app-debug.apk
```

## 数据更新

当前 APK 内置数据来自桌面端主库：

```text
D:\vb\data\workout.db
```

运行 `build-apk.ps1` 会自动执行：

- 同步 `fitness_tracker/config/exercises.json` 到 Android `Normalizer.java`
- 对桌面 SQLite 做 WAL checkpoint
- 复制最新 `workout.db` 到 `app/src/main/assets/workout.db`
- 构建 `app/build/outputs/apk/debug/app-debug.apk`

如果手机上已经安装过旧版本，新版会在启动时把内置库中缺失的训练记录合并进本地数据库，而不是覆盖用户在手机上新增或修改的数据。
