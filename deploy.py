import os
import re
import subprocess

subprocess.run(["git", "fetch"], check=True)
subprocess.run(["git", "reset", "--hard", "origin/trunk"], check=True)


def get_comment_syntax(filename):
    ext = os.path.splitext(filename)[1]
    if ext in [".js", ".ts"]:
        return "// start devb", "// end devb"
    elif ext in [".py"]:
        return "# start devb", "# end devb"
    elif ext in [".html"]:
        return "<!-- start devb -->", "<!-- end devb -->"
    elif ext in [".css"]:
        return "/* start devb ", "/* end devb */"
    else:
        return None, None

def remove_dev_blocks(file_path, start_comment, end_comment):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = rf"{re.escape(start_comment)}.*?{re.escape(end_comment)}\\n?"
    updated_content = re.sub(pattern, "", content, flags=re.DOTALL)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(updated_content)


for file in os.listdir("."):
    if os.path.isfile(file):
        start_comment, end_comment = get_comment_syntax(file)
        if start_comment and end_comment:
            remove_dev_blocks(file, start_comment, end_comment)


subprocess.run(["touch", "/var/www/som_dupunkto_org_wsgi.py"], check=True)
