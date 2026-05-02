# 健身趋势实时计算 - 原型框架

这是一个面向 Windows 的本地训练记录原型，用来按 **单组** 记录你的训练，并实时生成趋势图。

当前框架已经支持：

- 每做一组就记录一次
- 记录时间轴、部位、动作、重量、次数、组序号、备注
- SQLite 本地持久化
- 按天 / 周 / 月查看训练量趋势
- 查看各部位训练量分布
- 查看单个动作的重量 / 估算 1RM / 训练量趋势
- 查看每个动作最大重量按周 / 按月的提升百分比
- 导入审计，区分 Obsidian 与 OPPO 云便签补导入来源
- 查看最近记录并删除误录

## 推荐用法

例如你今天 `2026-04-24 17:00` 做杠铃卧推：

- 第 1 组：`杠铃卧推 / 胸 / 70kg / 10 次 / 第 1 组`
- 第 2 组：再录一条
- ...
- 第 5 组：再录一条

系统会自动把这些记录纳入天、周、月统计。

## 运行方式

先进入项目目录：

```powershell
cd D:\vb
```

创建并激活虚拟环境后安装依赖：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

启动应用：

```powershell
streamlit run app.py
```

如果 PowerShell 阻止激活脚本，也可以直接这样运行：

```powershell
D:\vb\.venv\Scripts\python.exe -m pip install -r D:\vb\requirements.txt
D:\vb\.venv\Scripts\python.exe -m streamlit run D:\vb\app.py
```

## 数据文件

本地数据库路径：

`D:\vb\data\workout.db`

当前确认数据范围：

- 最早训练：`2025-06-08 07:52`
- 最近训练：`2026-04-22 20:00`
- 有效训练组数：`2082`

打包版数据库路径：

`D:\vb\dist\FitnessTracker\data\workout.db`

## 打包成 EXE

已经补好 Windows 启动器：

- [launcher.py](</D:/vb/launcher.py:1>) 会自动启动本地服务并打开浏览器
- [build_exe.ps1](</D:/vb/build_exe.ps1:1>) 用来打包 `exe`

执行：

```powershell
cd D:\vb
.\build_exe.ps1
```

打包完成后，启动文件在：

`D:\vb\dist\FitnessTracker\FitnessTracker.exe`

双击即可启动。当前 EXE 使用 Windows 原生 WebView2 桌面窗口承载界面，不再自动打开 Chrome 或默认浏览器。

## 完整功能

当前版本已实现：

1. 同一训练 session 的自动分组（90 分钟间隔）
2. 常用动作快捷录入（快捷模式，从最近动作中选择）
3. 完整的趋势与科学指标：
   - 训练量趋势（天/周/月）
   - PR 记录（估算 1RM，Epley/Brzycki 双公式）
   - 动作最大重量提升百分比（周/月对比）
   - ACSM 次数区间分布
   - HHS 每周力量训练频率
   - Schoenfeld 部位周训练量（10 组参考线）
   - 负荷变化检测（急慢性工作量比 ACWR）
   - 恢复间隔提示（<48h 同部位检测）
   - 渐进加重候选推荐（连续 2 次 12+ rep）
4. 动作名称规范化（错字纠正，不改写原始数据）
5. 导入审计（区分 Obsidian / OPPO 云便签来源）
6. CSV 导出
7. Windows EXE 桌面程序（原生 WebView2 窗口）
8. Android 原生 App（共享 SQLite schema + 动作配置）
