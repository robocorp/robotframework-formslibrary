#  This file is bases upon https://github.com/robotframework/remoteswinglibrary/blob/master/src/main/python/RemoteSwingLibrary.py
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import FormsLibrary_Keywords
from contextlib import contextmanager
import inspect
import math
import os
import sys
import tempfile
import threading
import time
import traceback


IS_PYTHON3 = sys.version_info[0] >= 3
if IS_PYTHON3:
    import socketserver as SocketServer
    from xmlrpc.client import ProtocolError
else:
    import SocketServer
    from xmlrpclib import ProtocolError
import uuid

from robot.errors import HandlerExecutionFailed, TimeoutError
from robot.libraries.BuiltIn import BuiltIn
from robot.libraries.Process import Process
from robot.libraries.Remote import Remote
from robot.running import EXECUTION_CONTEXTS
from robot.running.namespace import IMPORTER
from robot.running.testlibraries import TestLibrary
from robot.libraries.BuiltIn import BuiltIn, run_keyword_variant
from robot.utils import timestr_to_secs, get_link_path
from robotbackgroundlogger import BackgroundLogger
from robot.api import logger as defaultLogger

logger = BackgroundLogger()

try:
    from robot.libraries.BuiltIn import RobotNotRunningError
except ImportError:  # Support RF < 2.8.5
    RobotNotRunningError = AttributeError


class AgentList(object):
    NEW = 'NEW'
    OLD = 'OLD'

    def __init__(self):
        self._remote_agents = []
        self.agent_received = threading.Event()
        self._lock = threading.RLock()

    def append(self, address, name):
        with self._lock:
            self.agent_received.set()
            self._remote_agents.append((address, name, self.NEW))

    def remove(self, address, name, age):
        with self._lock:
            self._remote_agents.remove((address, name, age))

    def get(self, accept_old):
        with self._lock:
            logger.log_background_messages()
            return [(address, name, age) for (address, name, age) in self._remote_agents
                    if accept_old or age == self.NEW]

    def set_received_to_old(self):
        with self._lock:
            self.agent_received.clear()
            for index, (address, name, age) in enumerate(self._remote_agents):
                self._remote_agents[index] = (address, name, self.OLD)


REMOTE_AGENTS_LIST = AgentList()

class SimpleServer(SocketServer.StreamRequestHandler):

    def handle(self):
        data = self.rfile.readline()[:-1]
        fields = data.decode().split(':')
        if fields[0] == 'PORT':
            port = fields[1]
            name = ':'.join(fields[2:])
            address = ':'.join([self.client_address[0], port])
            logger.debug('Registered java formslibrary agent "%s" at %s' % \
                         (name, address))
            REMOTE_AGENTS_LIST.append(address, name)
        elif fields[0] == 'DIALOG':
            title = ':'.join(fields[1:])
            logger.info('Security Warning "%s" was accepted automatically' % title)
        else:
            logger.debug('Unknown message "%s"' % fields[0])


class InvalidURLException(Exception):
    pass


class _RobotImporterWrapper(object):
    def remove_library(self, name, args):
        lib = TestLibrary(name, args, None, create_handlers=False)
        key = (name, lib.positional_args, lib.named_args)
        self._remove_library(key)

    def _remove_library(self, key):
        raise NotImplementedError()


class Robot26ImporterWrapper(_RobotImporterWrapper):
    def _remove_library(self, key):
        if key in IMPORTER._library_cache:
            index = IMPORTER._library_cache._keys.index(key)
            IMPORTER._library_cache._keys.pop(index)
            IMPORTER._library_cache._items.pop(index)


class OldRobotImporterWrapper(_RobotImporterWrapper):
    def _remove_library(self, key):
        if IMPORTER._libraries.has_key(key):  # key in dict doesn't work here
            index = IMPORTER._libraries._keys.index(key)
            IMPORTER._libraries._keys.pop(index)
            IMPORTER._libraries._libs.pop(index)


class RobotLibraryImporter(object):
    """Class for manipulating Robot Framework library imports during runtime"""

    args = ()

    def set_args(self, port=None, aphost='127.0.0.1', apport=None, debug=False, close_security_dialogs=False, __reload=True):
        self.args = (port, aphost, apport, debug, close_security_dialogs, __reload)

    def re_import_formslibrary(self):
        if EXECUTION_CONTEXTS.current is None:
            return
        name = 'FormsLibrary'
        self._remove_lib_from_current_namespace(name)
        self._import_wrapper().remove_library(name, [])
        BuiltIn().import_library(name, *self.args)

    def _import_wrapper(self):
        if hasattr(IMPORTER, '_library_cache'):
            return Robot26ImporterWrapper()
        return OldRobotImporterWrapper()

    def _remove_lib_from_current_namespace(self, name):
        ns = EXECUTION_CONTEXTS.current.namespace
        if hasattr(ns, '_kw_store'):  # RF 2.8.6+
            testlibs = ns._kw_store.libraries
        else:
            testlibs = ns._testlibs
        if name in testlibs:
            testlibs.pop(name)


class FormsLibraryTimeoutError(RuntimeError):
    pass


class FormsLibrary(object):
    """Robot Framework library leveraging Java-agents to run [https://github.com/robotframework/SwingLibrary|SwingLibrary]
    keywords on Java-processes.

    To take the library in to use add formslibrary-[version].jar to PYTHONPATH.

    The library contains a simple socket server to communicate with Java agents. When taking the library into use,
    you can specify the port this server uses. Providing the port is optional. If you do not provide one,
    FormsLibrary will ask the OS for an unused port.

    Keywords directly offered by this library on top of SwingLibrary keywords are:
    - [#Application Started|Application Started]
    - [#Ensure Application Should Close|Ensure Application Should Close]
    - [#Log Java System Properties|Log Java System Properties]
    - [#Set Java Tool Options|Set Java Tool Options]
    - [#Start Application|Start Application]
    - [#System Exit|System Exit]
    - [#Switch To Application|Switch To Application]
    - [#Connect To Application|Connect To Application]

    FormsLibrary also introduces two global variables that can be used during testing:
    - ${REMOTESWINGLIBRARYPATH} the location of the formslibrary jar file.
    - ${REMOTESWINGLIBRARYPORT} port used by the agents to communicate with the library - this is needed if a java agent
    is started for example from another machine.

    [https://github.com/ombre42/jrobotremoteserver|jrobotremoteserver]
    that is used by FormsLibrary also offers a keyword:
    - [#Stop Remote Server|Stop Remote Server]

    Following SwingLibrary Keywords are not available through FormsLibrary:
    - Launch Application
    - SwingLibrary version of Start Application
    - Start Application In Separate Thread

    NOTE! [#Get Table Cell Property|Get Table Cell Property] will return the string representation of that property
    and not the actual object. Complex objects are not passed through Remote library interface.

    Examples:
    | * Settings * |
    | Library | FormsLibrary |
    | * Test Cases * |
    | Testing java application |
    | | Start Application | myjavaapp | java -jar myjava.jar |
    | | Select Window  | My App |
    | | Ensure Application Should Close | 60 seconds | Push Button | Exit |


    """

    ROBOT_LIBRARY_SCOPE = 'GLOBAL'
    KEYWORDS = ['system_exit', 'start_application', 'application_started', 'switch_to_application',
                'ensure_application_should_close', 'log_java_system_properties', 'set_java_tool_options',
                'connect_to_application']
    REMOTES = {}
    CURRENT = None
    PROCESS = Process()
    ROBOT_NAMESPACE_BRIDGE = RobotLibraryImporter()
    TIMEOUT = 60
    PORT = None
    APHOST = None
    APPORT = None
    AGENT_PATH = os.path.abspath(os.path.dirname(__file__))
    _output_dir = ''

    def __init__(self, port=None, aphost='127.0.0.1', apport=None, debug=False,
                 close_security_dialogs=False, __reload=False, agentlib_port=8000):
        """
        *port*: optional port for the server receiving connections from remote agents

        *apport*: optional port for server receiving connections of remote agent.
        Should be used if you want to reconnect to same application between robot runs.

        *aphost*: opptional network address of application we want to connect into

        *debug*: optional flag that will start agent in mode with more logging for troubleshooting (set to TRUE to enable)

        *close_security_dialogs*: optional flag for automatic security dialogs closing (set to TRUE to enable)

        NOTE! with special value 'TEST' starts a test application for documentation generation
        purposes `python -m robot.libdoc FormsLibrary::TEST FormsLibrary.html`

        NOTE! FormsLibrary is a so called Global Scope library. This means when it is imported once it will be
        available until end of robot run. If Robot encounters another import of FormsLibrary with different
        import parameters the library will be reloaded and new options will be in use. You should be careful if you
        import FormsLibrary with different options in multiple test suites and resources.

        """
        if not __reload:
            FormsLibrary.CURRENT = None
            global REMOTE_AGENTS_LIST
            REMOTE_AGENTS_LIST = AgentList()
            FormsLibrary.PORT = None
        self.ROBOT_NAMESPACE_BRIDGE.set_args(port, aphost, apport, debug, close_security_dialogs)
        if FormsLibrary.PORT is None:
            FormsLibrary.PORT = self._start_port_server(0 if port == 'TEST' else port or 0)
        FormsLibrary.APHOST = aphost
        FormsLibrary.APPORT = apport
        self._create_env(bool(debug), bool(close_security_dialogs), agentlib_port)
        if port == 'TEST':
            self.start_application('docgenerator', 'java -jar %s' % FormsLibrary.AGENT_PATH, timeout=4.0)

    @property
    def current(self):
        if not self.CURRENT:
            return None
        return self.REMOTES[self.CURRENT][0]

    def _start_port_server(self, port):
        address = ('0.0.0.0', int(port))
        server = SocketServer.TCPServer(address, SimpleServer)
        server.allow_reuse_address = True
        #t = threading.Thread(name="FormsLibrary registration server thread",
        #                     target=server.serve_forever)
        t = threading.Thread(name="FormsLibrary registration server thread",
                             target=server.serve_forever, args=(0.01,))
        t.setDaemon(True)
        t.start()
        return server.server_address[1]

    def _create_env(self, debug, close_security_dialogs, agentlib_port):
        agent_command = ' -agentlib:jdwp=transport=dt_socket,address=%s,server=y,suspend=n -javaagent:"%s"=127.0.0.1:%s' % (agentlib_port, FormsLibrary.AGENT_PATH, FormsLibrary.PORT)
        if FormsLibrary.APPORT:
            agent_command += ':APPORT=%s' % FormsLibrary.APPORT
        if debug:
            agent_command += ':DEBUG'
        if close_security_dialogs:
            agent_command += ':CLOSE_SECURITY_DIALOGS'
        self._agent_command = agent_command
        try:
            BuiltIn().set_global_variable('\${REMOTESWINGLIBRARYPATH}', self._escape_path(FormsLibrary.AGENT_PATH))
            BuiltIn().set_global_variable('\${REMOTESWINGLIBRARYPORT}', FormsLibrary.PORT)
            self._output_dir = BuiltIn().get_variable_value('${OUTPUTDIR}')
        except RobotNotRunningError:
            pass
        logger.info(agent_command)


    def _escape_path(self, text):
        return text.replace("\\","\\\\")

    @contextmanager
    def _agent_java_tool_options(self):
        old_tool_options = os.environ.get('JAVA_TOOL_OPTIONS', '')
        old_options = os.environ.get('_JAVA_OPTIONS', '')
        logger.debug("Picked old JAVA_TOOL_OPTIONS='%s'" % old_tool_options)
        logger.debug("Picked old _JAVA_OPTIONS='%s'" % old_options)
        self.set_java_tool_options()
        try:
            yield
        finally:
            os.environ['JAVA_TOOL_OPTIONS'] = old_tool_options
            os.environ['_JAVA_OPTIONS'] = old_options
            logger.debug("Returned old JAVA_TOOL_OPTIONS='%s'" % old_tool_options)
            logger.debug("Returned old _JAVA_OPTIONS='%s'" % old_options)

    def set_java_tool_options(self):
        """Sets the JAVA_TOOL_OPTIONS to include FormsLibrary Agent and
        the _JAVA_OPTIONS to set a temporary policy granting all permissions.

        FormsLibrary Agent is normally enabled by `Start Application` by
        setting the JAVA_TOOL_OPTIONS environment variable only during
        that keyword call. So java processes started by other commands wont
        normally use the FormsLibrary Agent. This keyword sets that same
        environment variable to be used always. So all java processes started
        after this will use the Agent. This methods also creates temporary
        Java policy file which grants all permissions. This file is set as
        policy for each java command call.
        """
        os.environ['JAVA_TOOL_OPTIONS'] = self._agent_command
        logger.info("Set JAVA_TOOL_OPTIONS='%s'" % self._agent_command)
        with tempfile.NamedTemporaryFile(prefix='grant_all_', suffix='.policy', delete=False) as t:
            text = b"""
                grant {
                    permission java.security.AllPermission;
                };
                """
            t.write(text)
        java_policy = '-Djava.security.policy="%s"' % t.name
        variables = BuiltIn().get_variables()
        output_dir = variables['${OUTPUTDIR}']
        robot_output_dir = ' -Drobot.output_dir="%s"' % output_dir
        os.environ['_JAVA_OPTIONS'] = java_policy + robot_output_dir
        logger.info("Set _JAVA_OPTIONS='%s'" % os.environ['_JAVA_OPTIONS'])


    def start_application(self, alias, command, timeout=60, name_contains=None):
        """Starts the process in the `command` parameter  on the host operating system.
        The given alias is stored to identify the started application in FormsLibrary.

        timeout (default 60) is timeout in seconds.
        name_contains is a text that must be part of the name of the java process that we are connecting to.
        name_contains helps in situations where multiple java-processes are started.
        To see the name of the connecting java agents run tests with --loglevel DEBUG.

        """
        stdout = "remote_stdout.txt"
        stderr = "remote_stderr.txt"
        logger.info('<a href="%s">Link to stdout</a>' % stdout, html=True)
        logger.info('<a href="%s">Link to stderr</a>' % stderr, html=True)



        print("starting process ", command )
        REMOTE_AGENTS_LIST.set_received_to_old()
        with self._agent_java_tool_options():
            self.PROCESS.start_process(command, alias=alias, shell=True,
                                       stdout=self._output(stdout),
                                       stderr=self._output(stderr))
        try:
            self._application_started(alias, timeout=timeout, name_contains=name_contains, accept_old=False)
        except TimeoutError:
            raise
        except Exception:
            logger.info("Failed to start application: %s" % traceback.format_exc())
            # FIXME: this may hang, how is that possible?
            result = self.PROCESS.wait_for_process(timeout=0.01)
            if result:
                logger.info('STDOUT: %s' % result.stdout)
                logger.info('STDERR: %s' % result.stderr)
            else:
                logger.info("Process is running, but application startup failed")
            raise

    def connect_to_application(self, alias, timeout=60, name_contains=None):
        """Connects to application that was started in earlier RobotFramework run.
        *apport* import option needs to be set to use this keyword.
        Application that we want to connect into needs to be started by Start Application keyword when using same *apport* value.
        """
        try:
            self._application_started(alias, timeout=timeout, name_contains=name_contains, accept_old=True)
        except TimeoutError:
            raise
        except Exception:
            logger.info("Failed to connect to application: %s" % traceback.format_exc())
            result = self.PROCESS.wait_for_process(timeout=0.01)
            if result:
                logger.info('STDOUT: %s' % result.stdout)
                logger.info('STDERR: %s' % result.stderr)
            else:
                logger.info("Process is running, but application startup failed")
            raise

    def _output(self, filename):
        return os.path.join(self._output_dir, filename)

    def application_started(self, alias, timeout=60, name_contains=None):
        """Detects new FormsLibrary Java-agents in applications that are started without
        using the Start Application -keyword. The given alias is stored to identify the
        started application in FormsLibrary.
        Subsequent keywords will be passed on to this application."""
        self._application_started(alias, timeout, name_contains, accept_old=True)

    def _application_started(self, alias, timeout=60, name_contains=None, accept_old=True):
        self.TIMEOUT = timestr_to_secs(timeout)
        if (FormsLibrary.APPORT):
            url = '%s:%s'%(FormsLibrary.APHOST, FormsLibrary.APPORT)
        else:
            url = self._get_agent_address(name_contains, accept_old)
        logger.info('connecting to started application at %s' % url)
        self._initialize_remote_libraries(alias, url)
        FormsLibrary.CURRENT = alias
        logger.debug('modifying robot framework namespace')
        self.ROBOT_NAMESPACE_BRIDGE.re_import_formslibrary()
        logger.info('connected to started application at %s' % url)

    def _initialize_remote_libraries(self, alias, url):
        swinglibrary = Remote(url)
        logger.debug('remote swinglibrary instantiated')
        services = Remote(url + '/services')
        logger.debug('remote services instantiated')
        self.REMOTES[alias] = [swinglibrary, services]

    def _get_agent_address(self, name_pattern, accept_old):
        while True:
            if not REMOTE_AGENTS_LIST.get(accept_old):
                REMOTE_AGENTS_LIST.agent_received.clear()
            REMOTE_AGENTS_LIST.agent_received.wait(timeout=self.TIMEOUT)
            if not REMOTE_AGENTS_LIST.agent_received.isSet():
                raise FormsLibraryTimeoutError('Agent port not received before timeout')
            for address, name, age in reversed(REMOTE_AGENTS_LIST.get(accept_old)):
                if name_pattern is None or name_pattern in name:
                    REMOTE_AGENTS_LIST.remove(address, name, age)
                    return address
            time.sleep(0.1)

    def _ping_until_timeout(self, timeout):
        timeout = float(timeout)
        delta = min(0.1, timeout)
        endtime = timeout+time.time()
        while endtime > time.time():
            self._run_from_services('ping')
            time.sleep(delta)

    def _run_from_services(self, kw, *args, **kwargs):
        return self.REMOTES[FormsLibrary.CURRENT][1].run_keyword(kw, args, kwargs)

    @run_keyword_variant(resolve=1)
    def ensure_application_should_close(self, timeout, kw, *args):
        """ Runs the given keyword and waits until timeout for the application to close .
        If the application doesn't close, the keyword will take a screenshot and close the application
        and after that it will fail.
        In many cases calling the keyword that will close the application under test brakes the remote connection.
        This exception is ignored as it is expected by this keyword.
        Other exceptions will fail this keyword as expected.
        """
        with self._run_and_ignore_connection_lost():
            BuiltIn().run_keyword(kw, *args)
        try:
            self._application_should_be_closed(timeout=timestr_to_secs(timeout))
        except FormsLibraryTimeoutError as t:
            logger.warn('Application is not closed before timeout - killing application')
            self._take_screenshot()
            self.system_exit()
            raise

    def _take_screenshot(self):
        logdir = self._get_log_dir()
        filepath = os.path.join(logdir, 'formslibrary-screenshot%s.png' % int(time.time()*1000))
        self._run_from_services('takeScreenshot', filepath)
        logger.info('<img src="%s"></img>' % get_link_path(filepath, logdir), html=True)

    def _get_log_dir(self):
        variables = BuiltIn().get_variables()
        logfile = variables['${LOG FILE}']
        if logfile != 'NONE':
            return os.path.dirname(logfile)
        return variables['${OUTPUTDIR}']

    def _application_should_be_closed(self, timeout):
        with self._run_and_ignore_connection_lost():
            self._ping_until_timeout(timeout)
            raise FormsLibraryTimeoutError('Application was not closed before timeout')

    @contextmanager
    def _run_and_ignore_connection_lost(self):
        try:
            yield
        except RuntimeError as r: # disconnection from remotelibrary
            if 'Connection to remote server broken:' in r.args[0]:
                logger.info('Connection died as expected')
                return
            raise
        except HandlerExecutionFailed as e: # disconnection from xmlrpc wrapped in robot keyword
            if any(elem in e.args[0] for elem in ('Connection to remote server broken:', 'ProtocolError')):
                logger.info('Connection died as expected')
                return
            raise
        except ProtocolError as r: # disconnection from xmlrpc in jython on some platforms
            logger.info('Connection died as expected')
            return

    def system_exit(self, exit_code=1):
        """ Uses the FormsLibrary java agent to call system exit for the current java application.
        """
        with self._run_and_ignore_connection_lost():
            self._run_from_services('systemExit', exit_code)

    def switch_to_application(self, alias):
        """Switches between applications that are known to FormsLibrary.
        The application is identified using the alias.
        Subsequent keywords will be passed on to this application."""
        FormsLibrary.CURRENT = alias

    def log_java_system_properties(self):
        """ log and return java properties and environment information from the current java application.
        """
        env = self._run_from_services('getEnvironment')
        logger.info(env)
        return env

    def get_keyword_names(self):
        # get_keyword names takes argument `attempts` which makes it
        # wait 0,1,2,3,4,...,attempts-1 seconds in those attempts
        # we want to make total wait time to be close to original TIMEOUT
        # to do it we find minimal n which satisfies ((n)*(n-1))/2 >= TIMEOUT
        # solution is ceil(sqrt(TIMEOUT*2*4+1)/2+0.5)
        attempts = int(math.ceil(math.sqrt(FormsLibrary.TIMEOUT*2*4+1)/2+0.5))
        overrided_keywords = ['startApplication', 'launchApplication', 'startApplicationInSeparateThread']

        if self.current:
            return FormsLibrary.KEYWORDS + [kw for
                                      kw in self.current.get_keyword_names(attempts=attempts)
                                      if kw not in overrided_keywords]
        return FormsLibrary.KEYWORDS + [kw for kw in FormsLibrary_Keywords.keywords
                                              if kw not in overrided_keywords]


    def get_keyword_arguments(self, name):
        if name in FormsLibrary.KEYWORDS:
            return self._get_args(name)
        if self.current:
            return self.current.get_keyword_arguments(name)
        return FormsLibrary_Keywords.keyword_arguments[name]

    def _get_args(self, method_name):
        spec = inspect.getargspec(getattr(self, method_name))
        args = spec[0][1:]
        if spec[3]:
            for i, item in enumerate(reversed(spec[3])):
                args[-i-1] = args[-i-1]+'='+str(item)
        if spec[1]:
            args += ['*'+spec[1]]
        if spec[2]:
            args += ['**'+spec[2]]
        return args

    def get_keyword_documentation(self, name):
        if name == '__intro__':
            return FormsLibrary.__doc__
        if name in FormsLibrary.KEYWORDS or name == '__init__':
            return getattr(self, name).__doc__
        if self.current:
            return self.current.get_keyword_documentation(name)
        return FormsLibrary_Keywords.keyword_documentation[name]

    def run_keyword(self, name, arguments, kwargs):
        if name.startswith("capture"):
            path = self.current.run_keyword(name, arguments, kwargs)
            defaultLogger.info(path, html=True)
            logger.info('<a href="%s"><img src="%s" width="800px"></a>' % (path, path), html=True)
            logger.info("<a href=\"%s\">Screenshot</a> saved." % (path), html=True)
            return path
        if name in FormsLibrary.KEYWORDS:
            return getattr(self, name)(*arguments, **kwargs)
        if self.current:
            return self.current.run_keyword(name, arguments, kwargs)
        if name in FormsLibrary_Keywords.keywords:
            raise Exception("To use this keyword, you need to connect to the application first.")
