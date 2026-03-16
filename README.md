这是一个 RF S参数分析工具，主要功能：
数据输入

支持拖拽或选择 Touchstone 文件（.s1p/.s2p/.s3p/.s4p）
可同时加载多个文件对比

图表显示

dB幅度图：显示 S参数随频率的幅度变化
Smith圆图：同步显示阻抗轨迹
两图可通过菜单独立开关

参数控制

自定义频率范围（Start/Stop）
自定义 Y 轴范围（dB Max/Min）
标记特定频率点（同时在 dB 图和 Smith 图上高亮）
支持 S11~S44 任意多参数同时显示


<img width="492" height="824" alt="image" src="https://github.com/user-attachments/assets/75a1a2a2-9658-46b9-ae84-5cd46f7bd7e7" /><img width="1263" height="773" alt="image" src="https://github.com/user-attachments/assets/a64c3f7d-4fa4-4328-b995-ed9e04605d63" />



曲线定制

每条曲线可独立修改颜色（拾色器）
可切换线型（实线、虚线、点划线等）
表格中显示各标记频率的 dB 值

<img width="809" height="211" alt="image" src="https://github.com/user-attachments/assets/51daa520-7426-4a2d-b8fc-e7ad1d46aca4" />

导出

一键保存整个界面截图到桌面（PNG）
标题可自定义编辑

<img width="237" height="126" alt="image" src="https://github.com/user-attachments/assets/fe117a2e-4c65-40ef-a35a-503365061924" />


适合用于天线、滤波器、匹配网络等射频器件的 S 参数快速查看与对比。

下图是我整机天线pi网匹配的一个案子，使用这个工具做报告是一个不可或缺的选择
<img width="2582" height="1682" alt="image" src="https://github.com/user-attachments/assets/fe67d50a-2716-44d3-be76-cd0230a5cbb6" />
使用这个匹配再对比Active TRP，阻抗匹配后，TRP变好了
<img width="1041" height="414" alt="image" src="https://github.com/user-attachments/assets/d9f27f39-a9fb-4036-8721-0aad2c70ee33" />




最后，再测量天线效率前，P1阶段使用短0.6mm天线明显2450MHz谐振，天线S11 2450MHz谐振。但是P2使用的结构和P1不一样

<img width="2400" height="1400" alt="P1 FF swap P2 MLB " src="https://github.com/user-attachments/assets/de32e6cb-6076-46e4-9a54-9c44995dc239" />

所以此时的短0.6mm天线谐振频率对应到2490MHz上了，通过HFSS仿真数据，天线比P1短0.3mm或者0.4mm会更好






