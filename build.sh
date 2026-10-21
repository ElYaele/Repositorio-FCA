#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py shell -c "from django.contrib.auth.models import User; u, _ = User.objects.get_or_create(username='Yaele', defaults={'email': 'jeremy.de@uabc.edu.mx'}); u.set_password('ElYaelexD22'); u.is_staff = True; u.is_superuser = True; u.is_active = True; u.save(); print('Superusuario Yaele configurado con exito.')"