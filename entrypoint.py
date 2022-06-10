#!/usr/bin/env python3

import aiohttp
from aiohttp import web
import argparse
import asyncio
import glob
import mimetypes
import os
import re
import requests
import subprocess
import sys
import tempfile
import yaml

REPO_DIR   = "/repo"
TOOLS_DIR  = "/tools"
SCRIPT_DIR = "scripts"
TX_PROXY   = "127.0.0.1:8080"
TX_SERVER  = "http://v4.combined.tx"
CONFIG_FILE = "qa.yaml"
class Printer:
    ''' Class to route and format output to the desired location '''

    ANSI_TO_HTML = {
        "0" : {
            "0": "black",
            "1": "darkred",
            "2": "green",
            "3": "orange",
            "4": "darkblue",
            "5": "purple",
            "6": "lightblue",
            "7": "lightgrey"
        },
        "1" : {
            "0": "black",
            "1": "red",
            "2": "lightgreen",
            "3": "yellow",
            "4": "blue",
            "5": "magenta",
            "6": "cyan",
            "7": "white"
        }
    }

    def __init__(self):
        self.socket = None
    
    def setSocket(self, socket):
        ''' Set a web socket to send the output to. '''
        self.socket = socket

    async def writeLine(self, message):
        """ Write a line to the terminal. If a web socket is set and available for writing, the output will be echoed
            there as well. """
        await self.write(message + "\n")

    async def write(self, message):
        """ Write out the output to the terminal. If a web socket is set and available for writing, the output will be
            echoed there as well. """
        print(message, end = '')

        if self.socket != None and not self.socket.closed:
            # Set the message to "terminal colors" (lightgrey on black). Rewrite all ANSI color codes to HTML tags.
            html_msg = re.sub('\x1b\[(0|1);3(.)m', self._ansiToHTML, message)
            html_msg = re.sub('\x1b\[0m', "</span><span style='color: lightgrey'>", html_msg)
            html_msg = f"<span style='color: lightgrey;'>{html_msg}</span>"

            await self.socket.send_json({
                "output": html_msg
            })
    
    def _ansiToHTML(self, match_obj):
        ''' Helper method to rewrite an ASNI color code to a HTML style tag. '''
        try:
            color = self.ANSI_TO_HTML[match_obj.group(1)][match_obj.group(2)]
        except KeyError:
            return ""
        
        return f"</span><span style='color: {color}'>"

class FileCollection(dict):
    def __init__(self, config, changed_only = True):
        if "patterns" in config:
            self.patterns = config["patterns"]
        else:
            self.patterns = []
        
        for pattern_name in self.patterns:
            self[pattern_name] = []
        
        if "main branch" in config:
            self.main_branch = config["main branch"]
        else:
            self.main_branch = "origin/main"

        self.changed_only = changed_only

    def setChangedOnly(self, changed_only):
        self.changed_only = changed_only
        
    def resolve(self):
        # Reset all file lists
        for pattern_name in self.keys():
            self[pattern_name] = []

        if self.changed_only:
            # If we're only interested in the files that are new or changed compared to the main branch, we first ask
            # git for a list of all these files, committed or not
            committed   = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACM", self.main_branch], capture_output = True)
            uncommitted = subprocess.run(["git", "ls-files", "--others"], capture_output = True)
            if committed and uncommitted:
                changed_files =  committed.stdout.decode("UTF-8").split("\n")
                changed_files += uncommitted.stdout.decode("UTF-8").split("\n")
        else:
            # Otherwise we need to keep track of the files that we already encountered
            combined = []
            
        for pattern_name in self.patterns:
            patterns = self.patterns[pattern_name]
            # Each pattern name can be associated with multiple patterns, so make sure we always have a list
            if type(patterns) == str:
                patterns = [patterns]
            
            # Now add all files that match the pattern and that have not been seen before
            for pattern in patterns:
                for file_name in glob.glob(pattern, recursive = True):
                    if self.changed_only:
                        if file_name in changed_files:
                            self[pattern_name].append(file_name)
                            changed_files.remove(file_name)                   
                    else:
                        if file_name not in combined:
                            self[pattern_name].append(file_name)
                            combined.append(file_name)

class StepExecutor:
    def __init__(self, config, file_collection, printer):
        if "steps" in config:
            self.steps = config["steps"]
        else:
            self.steps = []

        self.tx_disabled     = False
        self.file_collection = file_collection
        self.printer         = printer

        self.debug = False

        # Export the variables for external scripts to use
        os.environ["tools_dir"]  = TOOLS_DIR
        os.environ["work_dir"]   = REPO_DIR
        os.environ["script_dir"] = os.path.join(REPO_DIR, SCRIPT_DIR)
        os.environ["tx_proxy"]   = TX_PROXY
        os.environ["tx_server"]  = TX_SERVER
    
    def getSteps(self):
        return self.steps.keys()
    
    def setDebugging(self, debug):
        self.debug = debug
    
    def disableTerminology(self, tx_disabled = False):
        self.tx_disabled = tx_disabled

    async def execute(self, *step_names):
        os.environ["debug"] = "1" if self.debug else "0"
        os.environ["changed_only"] = "1" if self.file_collection.changed_only else "0"
        self.file_collection.resolve()
    
        overall_success = True
        for step_name in step_names:
            step = self.steps[step_name]
            
            await self.printer.writeLine("\033[1;37m+++ " + step_name + "\033[0m")
            
            files = []
            if "patterns" in step:
                patterns = step["patterns"]
                if type(patterns) == str:
                    patterns = [patterns]
                for pattern in patterns:
                    files += self.file_collection[pattern]
        
            if len(files) == 0:
                await self.printer.writeLine("Nothing to check, skipping")
            else:
                if "profile" in step:
                    overall_success &= await self._runValidator(step["profile"], files)
                elif "script" in step:
                    overall_success &= await self._runExternalCommand(step["script"], files)
    
        if overall_success:
            await self.printer.writeLine("All checks finished succesfully")
        else:
            await self.printer.writeLine("Not all checks finished successfully")
        
        return overall_success

    async def _runValidator(self, profile, files):
        out_file = tempfile.mkstemp(".xml")
        if self.tx_disabled:
            tx_opt = ["-tx", "n/a"]
        else:
            tx_opt = ["-proxy", TX_PROXY, "-tx", TX_SERVER]
        command = [
            "java", "-jar", "/tools/validator/validator.jar",
            '-version', "4.0.1",
            "-ig", "qa", "-ig", "resources", "-recurse",
            "-profile", profile] + tx_opt + [
            "-output", out_file[1]] + files
        
        suppress_output = False if self.debug else True
        result_validator = await self._popen(command, suppress_output=suppress_output)
        
        success = False
        if result_validator == 0:
            result = await self._popen(["python3", "/tools/hl7-fhir-validator-action/analyze_results.py",  "--colorize", "--fail-at", "error", "--ignored-issues", "known-issues.yml", out_file[1]])
            if result == 0:
                success = True
        elif not self.debug:
            await self.printer.writeLine("\033[0;33mThere was an error running the validator. Re-run with the --debug option to see the output.\033[0m")
        
        os.unlink(out_file[1])
        return success 
  
    async def _runExternalCommand(self, command, files):
        result = await self._popen(os.path.join(SCRIPT_DIR, command) + " " + " ".join(files), shell = True)
        return result == 0

    async def _popen(self, command, shell = False, suppress_output = False):
        ''' Helper method to open a subprocess, send the output to the Printer as it comes in, and return the results. '''
        if suppress_output:
            stdout = subprocess.DEVNULL
        else:
            stdout = subprocess.PIPE
        proc = subprocess.Popen(command, stdout = stdout, stderr = subprocess.STDOUT, universal_newlines = True, bufsize = 1, shell = shell)
        
        if not suppress_output:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                await self.printer.write(line)
        proc.wait()
        return proc.returncode

class QAServer:
    ''' Class to serve an interactive menu using a web interface. '''

    def __init__(self, executor):
        self.executor = executor

        self.app = web.Application()
        self.app.router.add_get("/ws",     self._handleWebsocket)
        self.app.router.add_get("/",       self._handleGet)
        self.app.router.add_get("/{file}", self._handleGet)
        self.app.router.add_post("/",      self._handlePost)

        self.ws = web.WebSocketResponse()
    
    def run(self):
        web.run_app(self.app, port = MENU_PORT)

    async def _handleWebsocket(self, request):
        ''' Create and return a websocket when getting a GET request on /ws '''
        if self.ws.closed:
            self.ws = web.WebSocketResponse()
        await self.ws.prepare(request)

        # We don't actually expect communication _from_ the socket, but this is the way to keep it open
        await self.ws.receive()

        return self.ws

    async def _handleGet(self, request):
        ''' Handle GET request, which we do expect in two flavors: on the base or on a particular file. Any other
            request will result in a 404. '''

        requested_file = request.match_info.get('file', 'index.html')
        try:
            content = open("/server/" + requested_file).read()
            content_type = mimetypes.guess_type("/server/" + requested_file)[0]
        except IOError:
            return web.Response(status = 404)    
        if requested_file == 'index.html':
            # The menu HTML. We need to insert the steps that we know of in the static file that's loaded from disk.
            content_type = 'text/html'

            content = content.replace('<a id="tx_proxy">', f'<a href="http://localhost:{TX_MENU_PORT}" target="_blank">')
            task_html = ""
            for step in self.executor.getSteps():
                task_html += f"<input type='checkbox' name='step_{step}'/>"
                # TODO: Sanitize input for name use
                task_html += f"<label for='step_{step}'>{step}</label><br />"
            content = content.replace('<legend>Perform steps:</legend>', "<legend>Perform steps:</legend>" + task_html)
        
        return web.Response(body = content, content_type = content_type)

    async def _handlePost(self, request):
        content = await request.post()

        if "check_what" in content:
            self.executor.file_collection.setChangedOnly(content["check_what"] == "changed")

        steps = []
        for key in content:
            if key.startswith("step_"):
                steps.append(key.replace("step_", ""))

        if "terminology" in content:
            if content["terminology"] == "disabled":
                self.executor.disableTerminology(True)
            else:
                self.executor.disableTerminology(False)

                # Always set the supplied NTS credentials again for an execution, as the user might have removed them
                # to check without the NTS
                nts_credentials = {
                    "user": content["nts_user"],
                    "pass": content["nts_pass"]
                }
                requests.post("http://v4.combined.tx/resetNTSCredentials",
                    data = nts_credentials,
                    proxies = {"http": TX_PROXY})

        if "debug" in content:
            self.executor.setDebugging(True)
        else:
            self.executor.setDebugging(False)
        
        self.executor.printer.setSocket(self.ws)
        asyncio.create_task(self._executeAndReport(steps))
        return web.Response()

    async def _executeAndReport(self, steps):
        """ Execute the QA tooling and report back the result when done using the open web socket. """
        await self.ws.send_json({"status": "running"})
        result = await executor.execute(*steps)
        status = "success" if result else "failure"
        await self.ws.send_json({"result": status})
           
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "Perform QA on FHIR materials")
    parser.add_argument("--menu", action = "store_true",
                        help = "Display a menu rather than running in batch mode")
    parser.add_argument("--steps", type = str, nargs = "*",
                        help = "The steps to execute (make sure to quote them if they contain spaces). If absent, all steps will be executed.")
    parser.add_argument("--changed-only", type = bool, default = False,
                        help = "Only validate changed files rather than all files (compared to the main branch)")
    parser.add_argument("--debug", action = "store_true",
                        help = "Display debugging information for when something goes wrong")
    args = parser.parse_args()

    try:
        MENU_PORT = os.environ["MENU_PORT"]
    except KeyError:
        MENU_PORT = 9000

    try:
        TX_MENU_PORT = os.environ["TX_MENU_PORT"]
    except KeyError:
        TX_MENU_PORT = 9001
    
    os.chdir(REPO_DIR)

    with open(CONFIG_FILE) as config_file:
        config = yaml.safe_load(config_file)
    file_collection = FileCollection(config, args.changed_only)
    printer = Printer()
    executor = StepExecutor(config, file_collection, printer)
    executor.setDebugging(args.debug)
   
    mitmweb = subprocess.Popen(["mitmweb", "--web-iface", "0.0.0.0", "--web-port", TX_MENU_PORT, "-s", "/tools/CombinedTX/CombinedTX.py", "-q"])

    if args.steps != None:
        steps = args.steps
    else:
        steps = executor.getSteps()
    
    if args.menu:
        menu = QAServer(executor)
        menu.run()
    else:
        result = asyncio.run(executor.execute(*steps))
        if not result:
            sys.exit(1)

    mitmweb.terminate()