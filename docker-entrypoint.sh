#!/bin/bash
set -e

# Enable core dumps
ulimit -c unlimited

# Try to set core pattern, but don't fail if we can't
if [ -w /proc/sys/kernel/core_pattern ]; then
    echo "/cores/core.%e.%p" > /proc/sys/kernel/core_pattern
else
    echo "Warning: Cannot modify core pattern (read-only filesystem). Core dumps will use default pattern."
fi

# Run the command with error handling
if ! "$@"; then
    EXIT_CODE=$?
    
    # If we have a core dump, analyze it
    CORE_FILE=$(find /cores -name "core.*" -type f -newer /proc/1/cmdline 2>/dev/null)
    if [ -n "$CORE_FILE" ]; then
        echo "Found core dump: $CORE_FILE"
        echo "Running GDB for analysis..."
        gdb python3 "$CORE_FILE" -ex "thread apply all bt" -ex "quit"
    fi
    
    exit $EXIT_CODE
fi 

# Core dump handling adds startup time and complexity
RUN mkdir -p /cores
ENV CORE_PATTERN="/cores/core.%e.%p" 