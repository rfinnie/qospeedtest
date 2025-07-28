# SPDX-PackageSummary: qospeedtest
# SPDX-FileCopyrightText: Copyright (C) 2019-2025 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

FROM python:3.12

COPY . /tmp/build
RUN pip install --no-cache-dir '/tmp/build[gunicorn]' && rm -rf /tmp/build

USER nobody
CMD [ "gunicorn", "-b", "0.0.0.0:8000", "-k", "gthread", "--error-logfile", "-", "--capture-output", "qospeedtest.wsgi:application" ]
EXPOSE 8000/tcp
