"""
AI Dev Terminal Manager - Production Ready
Works with or without VS Code, captures output
this can create new terminal in vs code, exicute commands , terminal output with python with out vs code terminal acess as it is secured 
"""

import os
import json
import shutil
import sys
import subprocess
from pathlib import Path


class ExtensionInstaller:
    """Install VS Code extension"""
    
    def __init__(self):
        self.ext_path = Path.home() / ".vscode" / "extensions" / "ai-dev-terminal-1.0.0"
    
    def is_installed(self):
        return self.ext_path.exists()
    
    def install(self):
        if self.is_installed():
            return True
        
        temp = Path("__temp_ext__")
        temp.mkdir(exist_ok=True)
        
        with open(temp / "package.json", "w") as f:
            json.dump({
                "name": "ai-dev-terminal",
                "version": "1.0.0",
                "engines": {"vscode": "^1.60.0"},
                "activationEvents": ["*"],
                "main": "./extension.js"
            }, f)
        
        with open(temp / "extension.js", "w") as f:
            f.write('''
const vscode = require('vscode');
const http = require('http');

let terminals = new Map();
let counter = 0;

function activate(context) {
    const server = http.createServer((req, res) => {
        if (req.method === 'POST') {
            let body = '';
            req.on('data', d => body += d);
            req.on('end', () => {
                try {
                    const result = handle(JSON.parse(body));
                    res.writeHead(200, {'Content-Type': 'application/json'});
                    res.end(JSON.stringify(result));
                } catch (e) {
                    res.writeHead(500);
                    res.end(JSON.stringify({error: e.message}));
                }
            });
        } else {
            res.writeHead(200);
            res.end('Running');
        }
    });
    
    server.listen(45678, 'localhost');
    context.subscriptions.push({dispose: () => server.close()});
}

function handle(data) {
    switch (data.action) {
        case 'create': return create(data.name);
        case 'run': return run(data.id, data.cmd);
        case 'monitor': return monitor(data.id);
        case 'list': return list();
        default: return {error: 'Unknown action'};
    }
}

function create(name) {
    counter++;
    const t = vscode.window.createTerminal(name || `Terminal-${counter}`);
    terminals.set(counter, {
        terminal: t,
        name: name,
        commands: [],
        created: Date.now()
    });
    t.show();
    return {success: true, id: counter, name: name};
}

function run(id, cmd) {
    const d = terminals.get(id);
    if (!d) return {error: 'Terminal not found'};
    
    d.commands.push({cmd: cmd, time: Date.now()});
    d.terminal.sendText(cmd);
    d.terminal.show();
    return {success: true};
}

function monitor(id) {
    const d = terminals.get(id);
    if (!d) return {error: 'Terminal not found'};
    
    return {
        success: true,
        id: id,
        name: d.name,
        commands: d.commands,
        active: d.terminal.exitStatus === undefined,
        uptime: Date.now() - d.created
    };
}

function list() {
    const arr = [];
    terminals.forEach((d, id) => {
        arr.push({
            id: id,
            name: d.name,
            commands: d.commands.length,
            active: d.terminal.exitStatus === undefined
        });
    });
    return {success: true, terminals: arr};
}

function deactivate() {}
module.exports = {activate, deactivate};
''')
        
        self.ext_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(temp, self.ext_path)
        shutil.rmtree(temp)
        
        print("✓ Extension installed. Reload VS Code: Ctrl+Shift+P → 'Reload Window'")
        return False


class TerminalBridge:
    """Communication bridge to VS Code extension"""
    
    def __init__(self):
        self.url = "http://localhost:45678"
    
    def is_ready(self):
        try:
            import urllib.request
            urllib.request.urlopen(self.url, timeout=1)
            return True
        except:
            return False
    
    def send(self, action, **kwargs):
        import urllib.request
        
        data = json.dumps({"action": action, **kwargs}).encode()
        try:
            req = urllib.request.Request(self.url, data=data, headers={'Content-Type': 'application/json'})
            res = urllib.request.urlopen(req, timeout=5)
            return json.loads(res.read())
        except:
            return {"error": "Extension not responding"}


class Terminal:
    """Main terminal control API"""
    
    def __init__(self, mode="auto"):
        """
        Args:
            mode: "vscode" | "system" | "auto"
        """
        self.mode = mode
        self.bridge = None
        self.processes = {}
        self.counter = 0
        
        # Try VS Code mode
        if mode in ["auto", "vscode"]:
            installer = ExtensionInstaller()
            
            if not installer.is_installed():
                if mode == "vscode":
                    installer.install()
                    sys.exit("Extension installed. Reload VS Code and run again.")
                else:
                    self.mode = "system"
            
            if self.mode != "system":
                self.bridge = TerminalBridge()
                
                if not self.bridge.is_ready():
                    if mode == "vscode":
                        sys.exit("Extension not running. Start VS Code and reload.")
                    else:
                        self.mode = "system"
    
    
    def create(self, name):
        """Create new terminal. Returns: terminal_id or None"""
        if self.mode in ["vscode", "auto"] and self.bridge and self.bridge.is_ready():
            result = self.bridge.send("create", name=name)
            if "error" not in result:
                return result.get("id")
        
        # System mode fallback
        self.counter += 1
        self.processes[self.counter] = {"name": name, "history": []}
        return self.counter
    
    
    def run(self, terminal_id, command, capture_output=False):
        """
        Run command in terminal
        
        Args:
            terminal_id: Terminal ID
            command: Command to run
            capture_output: Capture output (only system mode)
        
        Returns:
            - VS Code: True/False
            - System with capture: {"output": "...", "error": "...", "exit_code": 0}
            - System no capture: True/False
        """
        if self.mode in ["vscode", "auto"] and self.bridge and self.bridge.is_ready():
            result = self.bridge.send("run", id=terminal_id, cmd=command)
            return result.get("success", False)
        
        # System mode
        if capture_output:
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                output_data = {
                    "command": command,
                    "output": result.stdout,
                    "error": result.stderr,
                    "exit_code": result.returncode,
                    "success": result.returncode == 0
                }
                
                if terminal_id in self.processes:
                    self.processes[terminal_id]["history"].append(output_data)
                
                return output_data
                
            except Exception as e:
                return {"error": str(e), "success": False}
        else:
            subprocess.Popen(command, shell=True)
            return True
    
    
    def monitor(self, terminal_id):
        """
        Get terminal info for AI
        
        Returns:
            VS Code: {"id": 1, "commands": [...], "active": true, "uptime": 1234}
            System: {"id": 1, "history": [{"output": "...", "error": "..."}]}
        """
        if self.mode in ["vscode", "auto"] and self.bridge and self.bridge.is_ready():
            result = self.bridge.send("monitor", id=terminal_id)
            if "error" not in result:
                return result
        
        # System mode
        if terminal_id in self.processes:
            return {
                "id": terminal_id,
                "name": self.processes[terminal_id]["name"],
                "mode": "system",
                "history": self.processes[terminal_id]["history"]
            }
        return None
    
    
    def list(self):
        """List all terminals"""
        if self.mode in ["vscode", "auto"] and self.bridge and self.bridge.is_ready():
            result = self.bridge.send("list")
            if "error" not in result:
                return result.get("terminals", [])
        
        # System mode
        return [
            {"id": tid, "name": data["name"], "commands": len(data["history"])}
            for tid, data in self.processes.items()
        ]


# Demo
if __name__ == "__main__":
    print("="*60)
    print("Demo: System Mode (works without VS Code)")
    print("="*60)
    
    terminal = Terminal(mode="system")
    
    # Create terminal
    t1 = terminal.create("Test")
    print(f"✓ Created terminal: {t1}")
    
    # Run with output capture
    print("\n[Running: python --version]")
    result = terminal.run(t1, "python --version", capture_output=True)
    print(f"Output: {result['output'].strip()}")
    print(f"Exit code: {result['exit_code']}")
    
    print("\n[Running: echo Hello World]")
    result = terminal.run(t1, "echo Hello World", capture_output=True)
    print(f"Output: {result['output'].strip()}")
    
    # Monitor (AI reads this)
    print("\n[Monitor - Full History for AI:]")
    info = terminal.monitor(t1)
    print(json.dumps(info, indent=2))
    
    print("\n" + "="*60)
    print("✓ System mode works without VS Code!")
    print("✓ Captures all output for AI monitoring!")
    print("="*60)
    
    # Try VS Code mode
    print("\n[Trying VS Code mode...]")
    try:
        terminal_vscode = Terminal(mode="vscode")
        t2 = terminal_vscode.create("VS Code Terminal")
        terminal_vscode.run(t2, "echo VS Code terminal test")
        print("✓ VS Code mode working!")
    except SystemExit as e:
        print(f"VS Code mode: {e}")
