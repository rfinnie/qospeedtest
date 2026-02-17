# SPDX-PackageName: qospeedtest
# SPDX-PackageSupplier: Ryan Finnie <ryan@finnie.org>
# SPDX-PackageDownloadLocation: https://github.com/rfinnie/qospeedtest
# SPDX-FileCopyrightText: © 2019 Ryan Finnie <ryan@finnie.org>
# SPDX-License-Identifier: MPL-2.0

FROM python:3.12

COPY . /tmp/build
RUN pip install --no-cache-dir '/tmp/build[gunicorn]' && useradd -ms /bin/bash qospeedtest && rm -rf /tmp/build

USER qospeedtest
CMD [ "gunicorn", "-b", "0.0.0.0:8000", "-k", "gthread", "--error-logfile", "-", "--capture-output", "qospeedtest.wsgi:application" ]
EXPOSE 8000/tcp
