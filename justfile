os := `uname`

test regex="." *args='':
    #!/bin/sh
    GENERATE_REPORT=0 FORCE_COLOR=1 BETTER_EXCEPTIONS=1 uv run pytest ./tests -k {{regex}} {{args}}