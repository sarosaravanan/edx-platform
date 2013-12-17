"""
Send emails to users inviting them to add their course certificates to their
LinkedIn profiles.
"""

import json
import urllib

from courseware.courses import get_course_by_id
from django.core.management.base import BaseCommand
from django.template import Context
from django.template.loader import get_template
from optparse import make_option

from certificates.models import GeneratedCertificate
from ...models import LinkedIn

from . import LinkedinAPI


class Command(BaseCommand):
    """
    Django command for inviting users to add their course certificates to their
    LinkedIn profiles.
    """
    args = ''
    help = ('Sends emails to edX users that are on LinkedIn who have completed '
            'course certificates, inviting them to add their certificates to '
            'their LinkedIn profiles')
    option_list = BaseCommand.option_list + (
        make_option(
            '--grandfather',
            action='store_true',
            dest='grandfather',
            default=False,
            help="Creates aggregate invitations for all certificates a user "
                 "has earned to date and sends a 'grandfather' email.  This is "
                 "intended to be used when the feature is launched to invite "
                 "all users that have earned certificates to date to add their "
                 "certificates.  Afterwards the default, one email per "
                 "certificate mail form will be used."),)

    def handle(self, *args, **options):
        grandfather = options.get('grandfather', False)
        accounts = LinkedIn.objects.filter(has_linkedin_account=True)
        for account in accounts:
            emailed = json.loads(account.emailed_courses)
            user = account.user
            certificates = GeneratedCertificate.objects.filter(user=user)
            certificates = certificates.filter(status='downloadable')
            certificates = [cert for cert in certificates
                            if cert.course_id not in emailed]
            if not certificates:
                continue
            if grandfather:
                send_grandfather_email(user, certificates)
                emailed.extend([cert.course_id for cert in certificates])
            else:
                for certificate in certificates:
                    send_email(user, certificate)
                    emailed.append(certificate.course_id)
            account.emailed_courses = json.dumps(emailed)

def certificate_url(api, course, certificate, grandfather=False):
    """
    Generates a certificate URL based on LinkedIn's documentation.  The
    documentation is from a Word document: DAT_DOCUMENTATION_v3.12.docx
    """
    tracking_code = '-'.join([
        'eml',
        'prof',  # the 'product'--no idea what that's supposed to mean
        course.org,  # Partner's name
        course.number,  # Certificate's name
        'gf' if grandfather else 'T'])
    query = {
        'pfCertificationName': certificate.name,
        'pfAuthorityName': api.config['COMPANY_NAME'],
        'pfAuthorityId': api.config['COMPANY_ID'],
        'pfCertificationUrl': certificate.download_url,
        'pfLicenseNo': certificate.course_id,
        'pfCertStartDate': course.start.strftime('%Y%mI'),
        'pfCertFuture': certificate.created_date.strftime('%Y%m'),
        '_mSplash': '1',
        'trk': tracking_code,
        'startTask': 'CERTIFICATION_name',
        'force': 'true',
    }
    return 'http://www.linkedin.com/profile/guided?' + urllib.urlencode(query)


def send_grandfather_email(user, certificates):
    """
    Send the 'grandfathered' email informing historical students that they may
    now post their certificates on their LinkedIn profiles.
    """
    print "GRANDFATHER: ", user, certificates


def send_email(user, certificate):
    """
    Email a user that recently earned a certificate, inviting them to post their
    certificate on their LinkedIn profile.
    """
    api = LinkedinAPI()
    template = get_template("linkedin_email.html")
    course = get_course_by_id(certificate.course_id)
    url = certificate_url(api, course, certificate)
    context = Context({
        'student_name': user.profile.name,
        'course_name': certificate.name,
        'url': url})
    print template.render(context)
    print url