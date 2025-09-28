from IPython.display import display, HTML, FileLink, IFrame
import os

abs_html_path = os.path.abspath(
    r"C:\Users\86137\Desktop\owenrl\owenrl\test\merged_analysis_reports.html")
with open(abs_html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()
# 正确转义HTML内容
escaped_html = html_content.replace(
    "'", "&apos;").replace('"', "&quot;")

# 使用正确的iframe标签
display(HTML(f"""
<div style="margin: 20px 0; border: 1px solid #ddd; border-radius: 5px; padding: 10px;">
    <h4 style="margin-top: 0;">合并报告预览</h4>
    <iframe 
        srcdoc='{escaped_html}' 
        width="100%" 
        height="600" 
        frameborder="0"
        style="border: 1px solid #eee; border-radius: 3px;"
    ></iframe>
    <p style="font-size: 12px; color: #666; margin: 10px 0 0 0;">
        如果图表未正常显示，请点击上方链接查看完整报告
    </p>
</div>
"""))
