#!/bin/bash
export PYTHONIOENCODING=utf-8
export LANG=ru_RU.UTF-8
export LC_ALL=ru_RU.UTF-8
export LANGUAGE=ru_RU.UTF-8

# Проверяем наличие локали, если нет - используем стандартную
if ! locale -a | grep -i ru_RU > /dev/null; then
    echo "Русская локаль не найдена, используем en_US.UTF-8"
    export LANG=en_US.UTF-8
    export LC_ALL=en_US.UTF-8
fi

python bot.py
