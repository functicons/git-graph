This tool is used to generate the object graph of a Git repository. It can help Git learners better understand the Git data model through visualization. You can experiment with various git operations (e.g., add/delete/edit files or directories, merge branches, etc), commit, then run this tool to see what happened to the data in the .git directory under the hood.

Requirements: Python 3.5+, graphviz (OS package and Python package)

Usage: `python3.5 git-graph.py [git-repo-path]`

Sample output:

![sample](https://raw.githubusercontent.com/functicons/git-graph/master/samples/git_graph.png)

References on Git internals:
- [Pro Git- Git Internals - Git Objects](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects)
- [Understanding Git — Data Model](https://hackernoon.com/https-medium-com-zspajich-understanding-git-data-model-95eb16cc99f5)
- [Learning Git Internals by Example](http://teohm.com/blog/learning-git-internals-by-example/)
- [OSCON 2016: Dissecting Git's Guts - Git Internals - Emily Xie](https://www.youtube.com/watch?v=YUCwr1Y6bFI).
