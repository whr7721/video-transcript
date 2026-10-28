# 拾文自用接入

上游 https://github.com/haodongcui/md2card ，固定提交 f672126c5caba634244c34aebcd5c83e11f0cc52；MIT许可保留。
本地修改：从localStorage一次性接收拾文传来的Markdown，避免恢复旧草稿覆盖新传入内容。其余排版、分页、主题、本地图片和PNG ZIP复用上游。
构建：npm ci，然后npm run build。自用app挂载/cards/，排版入口/cards/app/。工作台“编辑稿转图文”、素材库“转图文卡片”会携带文字。图片需在排版工具中本地导入/匹配；不自动复制他人原图。
AI沿用拾文现有整理；先采用整理稿进入编辑稿再转卡片，未增加模型调用。导出浏览器实测仍待用户点验。
