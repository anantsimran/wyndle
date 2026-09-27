"""Wyndle -- ADHD-Aware Productivity System for the Terminal.

Architecture (v1.3.0)
---------------------

::

                                  cli.py
                      +------+-----+-----+------+------+
                      v      v     v     v      v      v
                 morning  start  wrap  break  stuck  status  reflect  daemon
                   |  |      |     | |    |      |      |       |       |
                   v  v      v     v v    v      v      v       v       v
                +--------------------------------------------------------------+
                |                      lib/ layer                               |
                |  +--------------+  +-------------+  +-----------+            |
                |  | markdown_dom |  | daily_notes |  |   timer   |            |
                |  |   (v1.3.0)  |  |             |  |           |            |
                |  +--------------+  +-------------+  +-----------+            |
                |         |                |             |                      |
                |  +--------------+       |              |                      |
                |  | task_notes   |-------+              |                      |
                |  +--------------+                      |                      |
                |         |              |               |                      |
                |         v              v               v                      |
                |  +----------+  +-----------+  +----------+                   |
                |  |  models  |  |   state   |  | notifier |                   |
                |  +----------+  +-----------+  +----------+                   |
                |                      |              |                         |
                |               +------+------+       |                        |
                |               v             v       v                        |
                |          time_utils      config   display                    |
                +--------------------------------------------------------------+

Data sync flow::

    Task Note (notes/tasks/)  --morning-->  Daily Note (notes/daily/)
                                            User edits subtask notes
    Task Note  <--wrap--  Daily Note + State (~/.wyndle/state/)

Parsing: markdown_dom.py provides DOM-based parser for plain Markdown.
Status tags (~open/~deferred/~future) live in task notes only.
"""

__version__ = "1.3.1"
