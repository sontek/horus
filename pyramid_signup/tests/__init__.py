import unittest
from webtest import TestApp
from sqlalchemy import engine_from_config
from pyramid import testing
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid_beaker import session_factory_from_settings
from pyramid.response import Response
from paste.deploy.loadwsgi import appconfig
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from zope.sqlalchemy import register

from mock import Mock
import os

from pyramid_signup.models import SUEntity
from pyramid_signup.interfaces import ISUSession

here = os.path.dirname(__file__)
settings = appconfig('config:' + os.path.join(here, '../../', 'test.ini'))

DBSession = scoped_session(sessionmaker())
register(DBSession)

class BaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = engine_from_config(settings, prefix='sqlalchemy.')
        cls.Session = sessionmaker()

    def setUp(self):
        self.config = testing.setUp()

        self.connection = connection = self.engine.connect()

        # begin a non-ORM transaction
        self.trans = connection.begin()

        # bind an individual Session to the connection
        self.session = self.Session(bind=connection)

        self.config.registry.registerUtility(self.session, ISUSession)

        SUEntity.metadata.bind=connection

    def tearDown(self):
        # rollback - everything that happened with the
        # Session above (including calls to commit())
        # is rolled back.
        testing.tearDown()
        self.trans.rollback()
        self.session.close()

class UnitTestBase(BaseTestCase):
    def get_csrf_request(self, post=None, request_method='GET'):
        csrf = 'abc'

        if not post:
            post = {}

        if not u'csrf_token' in post.keys():
            post.update({
                'csrf_token': csrf
            })

        request = testing.DummyRequest(post)

        request.session = Mock()
        csrf_token = Mock()
        csrf_token.return_value = csrf

        request.session.get_csrf_token = csrf_token
        request.method = request_method

        return request

class IntegrationTestBase(unittest.TestCase):
    def main(self, global_config, **settings):
        settings['su.using_tm'] = True

        config = global_config
        config.add_settings(settings)

        def index(request):
            return Response('index!')

        config.add_route('index', '/')
        config.add_view(index, route_name='index')

        authz_policy = ACLAuthorizationPolicy()
        config.set_authorization_policy(authz_policy)


        authn_policy = AuthTktAuthenticationPolicy('secret')
        config.set_authentication_policy(authn_policy)

        session_factory = session_factory_from_settings(settings)

        config.set_session_factory(session_factory)

#        config.include('pyramid_tm')

        config.registry.registerUtility(DBSession, ISUSession)

        if settings.get('su.require_activation', True):
            config.include('pyramid_mailer')

        config.include('pyramid_signup')

        app = config.make_wsgi_app()

        return app

    def setUp(self):
        self.engine = engine_from_config(settings, prefix='sqlalchemy.')
        self.config = testing.setUp()
        app = self.main(self.config, **settings)
        self.app = TestApp(app)
        self.connection = connection = self.engine.connect()

        self.session = app.registry.getUtility(ISUSession)
        self.session.configure(bind=connection)
        # begin a non-ORM transaction
        self.trans = connection.begin()

        SUEntity.metadata.bind=connection

    def tearDown(self):
        # rollback - everything that happened with the
        # Session above (including calls to commit())
        # is rolled back.
        testing.tearDown()
        self.trans.rollback()
        self.session.close()
