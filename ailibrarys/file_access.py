
"""
AI Dev Manager - Complete Terminal + File System Access
Gives AI full control to code with schemas and prompts
"""

import os
import json
import shutil
import sys
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Union
import time


# ============================================================================
# TERMINAL MANAGER (Enhanced from your original)
# ============================================================================

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
    """Terminal control with enhanced output capture"""
    
    def __init__(self, mode="auto"):
        self.mode = mode
        self.bridge = None
        self.processes = {}
        self.counter = 0
        
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
        """Create new terminal"""
        if self.mode in ["vscode", "auto"] and self.bridge and self.bridge.is_ready():
            result = self.bridge.send("create", name=name)
            if "error" not in result:
                return result.get("id")
        
        self.counter += 1
        self.processes[self.counter] = {"name": name, "history": []}
        return self.counter
    
    def run(self, terminal_id, command, capture_output=False, timeout=30):
        """Run command with optional output capture"""
        if self.mode in ["vscode", "auto"] and self.bridge and self.bridge.is_ready():
            result = self.bridge.send("run", id=terminal_id, cmd=command)
            return result.get("success", False)
        
        if capture_output:
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout
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
        """Get terminal history"""
        if self.mode in ["vscode", "auto"] and self.bridge and self.bridge.is_ready():
            result = self.bridge.send("monitor", id=terminal_id)
            if "error" not in result:
                return result
        
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
        
        return [
            {"id": tid, "name": data["name"], "commands": len(data["history"])}
            for tid, data in self.processes.items()
        ]


# ============================================================================
# FILE SYSTEM MANAGER (NEW - Complete file operations)
# ============================================================================

class FileSystem:
    """Complete file system access for AI"""
    
    def __init__(self, workspace_root: str = "."):
        """
        Args:
            workspace_root: Root directory for operations (security boundary)
        """
        self.workspace_root = Path(workspace_root).resolve()
        self.operation_log = []
    
    def _log(self, operation: str, path: str, success: bool, details: str = ""):
        """Log file operations for AI monitoring"""
        self.operation_log.append({
            "timestamp": time.time(),
            "operation": operation,
            "path": path,
            "success": success,
            "details": details
        })
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve path within workspace (security check)"""
        resolved = (self.workspace_root / path).resolve()
        if not str(resolved).startswith(str(self.workspace_root)):
            raise ValueError(f"Path outside workspace: {path}")
        return resolved
    
    # ========== READ OPERATIONS ==========
    
    def read_file(self, path: str, encoding: str = "utf-8") -> Dict:
        """
        Read file content
        
        Returns:
            {"success": True, "content": "...", "size": 1234}
        """
        try:
            file_path = self._resolve_path(path)
            
            if not file_path.exists():
                self._log("read", path, False, "File not found")
                return {"success": False, "error": "File not found"}
            
            content = file_path.read_text(encoding=encoding)
            self._log("read", path, True, f"Read {len(content)} chars")
            
            return {
                "success": True,
                "content": content,
                "size": len(content),
                "path": str(file_path.relative_to(self.workspace_root))
            }
        except Exception as e:
            self._log("read", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    def read_binary(self, path: str) -> Dict:
        """Read binary file"""
        try:
            file_path = self._resolve_path(path)
            
            if not file_path.exists():
                return {"success": False, "error": "File not found"}
            
            content = file_path.read_bytes()
            self._log("read_binary", path, True, f"Read {len(content)} bytes")
            
            return {
                "success": True,
                "content": content,
                "size": len(content)
            }
        except Exception as e:
            self._log("read_binary", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    def list_directory(self, path: str = ".", pattern: str = "*") -> Dict:
        """
        List directory contents
        
        Args:
            path: Directory path
            pattern: Glob pattern (e.g., "*.py", "**/*.js")
        
        Returns:
            {"success": True, "files": [...], "dirs": [...]}
        """
        try:
            dir_path = self._resolve_path(path)
            
            if not dir_path.exists():
                return {"success": False, "error": "Directory not found"}
            
            if not dir_path.is_dir():
                return {"success": False, "error": "Not a directory"}
            
            items = list(dir_path.glob(pattern))
            
            files = []
            dirs = []
            
            for item in items:
                rel_path = str(item.relative_to(self.workspace_root))
                info = {
                    "path": rel_path,
                    "name": item.name,
                    "size": item.stat().st_size if item.is_file() else 0
                }
                
                if item.is_file():
                    files.append(info)
                elif item.is_dir():
                    dirs.append(info)
            
            self._log("list", path, True, f"Found {len(files)} files, {len(dirs)} dirs")
            
            return {
                "success": True,
                "files": files,
                "dirs": dirs,
                "total": len(files) + len(dirs)
            }
        except Exception as e:
            self._log("list", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    def get_tree(self, path: str = ".", max_depth: int = 3, ignore: List[str] = None) -> Dict:
        """
        Get directory tree structure
        
        Args:
            path: Root path
            max_depth: Maximum depth
            ignore: List of patterns to ignore (e.g., ["node_modules", ".git"])
        """
        ignore = ignore or ["node_modules", ".git", "__pycache__", "venv", ".venv"]
        
        def build_tree(current_path: Path, depth: int = 0):
            if depth > max_depth:
                return None
            
            items = []
            try:
                for item in current_path.iterdir():
                    if any(ignored in item.name for ignored in ignore):
                        continue
                    
                    node = {
                        "name": item.name,
                        "type": "file" if item.is_file() else "dir",
                        "path": str(item.relative_to(self.workspace_root))
                    }
                    
                    if item.is_dir():
                        node["children"] = build_tree(item, depth + 1)
                    
                    items.append(node)
            except PermissionError:
                pass
            
            return items
        
        try:
            dir_path = self._resolve_path(path)
            tree = build_tree(dir_path)
            
            return {
                "success": True,
                "tree": tree,
                "root": path
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def file_exists(self, path: str) -> bool:
        """Check if file exists"""
        try:
            return self._resolve_path(path).exists()
        except:
            return False
    
    # ========== WRITE OPERATIONS ==========
    
    def write_file(self, path: str, content: str, encoding: str = "utf-8") -> Dict:
        """
        Write/create file
        
        Returns:
            {"success": True, "path": "...", "size": 1234}
        """
        try:
            file_path = self._resolve_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_path.write_text(content, encoding=encoding)
            self._log("write", path, True, f"Wrote {len(content)} chars")
            
            return {
                "success": True,
                "path": str(file_path.relative_to(self.workspace_root)),
                "size": len(content)
            }
        except Exception as e:
            self._log("write", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    def append_file(self, path: str, content: str, encoding: str = "utf-8") -> Dict:
        """Append to file"""
        try:
            file_path = self._resolve_path(path)
            
            with open(file_path, "a", encoding=encoding) as f:
                f.write(content)
            
            self._log("append", path, True, f"Appended {len(content)} chars")
            
            return {"success": True, "path": str(file_path.relative_to(self.workspace_root))}
        except Exception as e:
            self._log("append", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    def modify_file(self, path: str, old_content: str, new_content: str) -> Dict:
        """
        Find and replace in file (like code updates)
        
        Args:
            path: File path
            old_content: Content to find
            new_content: Replacement content
        """
        try:
            result = self.read_file(path)
            if not result["success"]:
                return result
            
            content = result["content"]
            
            if old_content not in content:
                return {"success": False, "error": "Content not found in file"}
            
            new_file_content = content.replace(old_content, new_content, 1)
            
            return self.write_file(path, new_file_content)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ========== DELETE OPERATIONS ==========
    
    def delete_file(self, path: str) -> Dict:
        """Delete file"""
        try:
            file_path = self._resolve_path(path)
            
            if not file_path.exists():
                return {"success": False, "error": "File not found"}
            
            if file_path.is_dir():
                return {"success": False, "error": "Use delete_directory for folders"}
            
            file_path.unlink()
            self._log("delete", path, True)
            
            return {"success": True, "path": path}
        except Exception as e:
            self._log("delete", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    def delete_directory(self, path: str, recursive: bool = False) -> Dict:
        """Delete directory"""
        try:
            dir_path = self._resolve_path(path)
            
            if not dir_path.exists():
                return {"success": False, "error": "Directory not found"}
            
            if not dir_path.is_dir():
                return {"success": False, "error": "Not a directory"}
            
            if recursive:
                shutil.rmtree(dir_path)
            else:
                dir_path.rmdir()
            
            self._log("delete_dir", path, True)
            
            return {"success": True, "path": path}
        except Exception as e:
            self._log("delete_dir", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    # ========== DIRECTORY OPERATIONS ==========
    
    def create_directory(self, path: str) -> Dict:
        """Create directory"""
        try:
            dir_path = self._resolve_path(path)
            dir_path.mkdir(parents=True, exist_ok=True)
            
            self._log("mkdir", path, True)
            
            return {"success": True, "path": str(dir_path.relative_to(self.workspace_root))}
        except Exception as e:
            self._log("mkdir", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    def copy_file(self, src: str, dest: str) -> Dict:
        """Copy file"""
        try:
            src_path = self._resolve_path(src)
            dest_path = self._resolve_path(dest)
            
            if not src_path.exists():
                return {"success": False, "error": "Source file not found"}
            
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest_path)
            
            self._log("copy", f"{src} -> {dest}", True)
            
            return {"success": True, "src": src, "dest": dest}
        except Exception as e:
            self._log("copy", f"{src} -> {dest}", False, str(e))
            return {"success": False, "error": str(e)}
    
    def move_file(self, src: str, dest: str) -> Dict:
        """Move/rename file"""
        try:
            src_path = self._resolve_path(src)
            dest_path = self._resolve_path(dest)
            
            if not src_path.exists():
                return {"success": False, "error": "Source file not found"}
            
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src_path, dest_path)
            
            self._log("move", f"{src} -> {dest}", True)
            
            return {"success": True, "src": src, "dest": dest}
        except Exception as e:
            self._log("move", f"{src} -> {dest}", False, str(e))
            return {"success": False, "error": str(e)}
    
    # ========== MONITORING ==========
    
    def get_operation_log(self, last_n: int = 50) -> List[Dict]:
        """Get recent file operations for AI monitoring"""
        return self.operation_log[-last_n:]
    
    def clear_log(self):
        """Clear operation log"""
        self.operation_log = []


# ============================================================================
# UNIFIED AI DEV MANAGER
# ============================================================================

class AIDevManager:
    """
    Complete AI development environment manager
    Combines Terminal + FileSystem for full AI control
    """
    
    def __init__(self, workspace_root: str = ".", terminal_mode: str = "auto"):
        """
        Args:
            workspace_root: Project root directory
            terminal_mode: "auto", "vscode", or "system"
        """
        self.terminal = Terminal(mode=terminal_mode)
        self.fs = FileSystem(workspace_root=workspace_root)
        self.workspace_root = Path(workspace_root).resolve()
    
    # ========== HIGH-LEVEL AI OPERATIONS ==========
    
    def create_project(self, project_name: str, project_type: str = "python") -> Dict:
        """
        Create new project with structure
        
        Args:
            project_name: Project folder name
            project_type: "python", "node", "react", etc.
        """
        templates = {
            "python": {
                "dirs": ["src", "tests", "docs"],
                "files": {
                    "README.md": f"# {project_name}\n\nPython project",
                    "requirements.txt": "",
                    ".gitignore": "venv/\n__pycache__/\n*.pyc\n.env\n",
                    "src/__init__.py": "",
                    "src/main.py": "def main():\n    print('Hello World')\n\nif __name__ == '__main__':\n    main()\n"
                }
            },
            "node": {
                "dirs": ["src", "tests"],
                "files": {
                    "README.md": f"# {project_name}\n\nNode.js project",
                    "package.json": json.dumps({
                        "name": project_name,
                        "version": "1.0.0",
                        "main": "src/index.js"
                    }, indent=2),
                    ".gitignore": "node_modules/\n.env\n",
                    "src/index.js": "console.log('Hello World');\n"
                }
            }
        }
        
        template = templates.get(project_type, templates["python"])
        
        try:
            # Create project directory
            self.fs.create_directory(project_name)
            
            # Create subdirectories
            for dir_name in template["dirs"]:
                self.fs.create_directory(f"{project_name}/{dir_name}")
            
            # Create files
            for file_path, content in template["files"].items():
                self.fs.write_file(f"{project_name}/{file_path}", content)
            
            return {
                "success": True,
                "project": project_name,
                "type": project_type,
                "path": str((self.workspace_root / project_name).resolve())
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def execute_workflow(self, workflow: List[Dict]) -> List[Dict]:
        """
        Execute a workflow of terminal + file operations
        
        Args:
            workflow: List of operations like:
                [
                    {"type": "terminal", "command": "npm install"},
                    {"type": "file", "action": "write", "path": "config.json", "content": "..."},
                    {"type": "terminal", "command": "npm test", "capture": True}
                ]
        
        Returns:
            List of results for each operation
        """
        results = []
        terminal_id = None
        
        for step in workflow:
            try:
                if step["type"] == "terminal":
                    if terminal_id is None:
                        terminal_id = self.terminal.create("AI Workflow")
                    
                    result = self.terminal.run(
                        terminal_id,
                        step["command"],
                        capture_output=step.get("capture", False)
                    )
                    results.append({"step": step, "result": result})
                
                elif step["type"] == "file":
                    action = step["action"]
                    
                    if action == "write":
                        result = self.fs.write_file(step["path"], step["content"])
                    elif action == "read":
                        result = self.fs.read_file(step["path"])
                    elif action == "delete":
                        result = self.fs.delete_file(step["path"])
                    elif action == "modify":
                        result = self.fs.modify_file(step["path"], step["old"], step["new"])
                    else:
                        result = {"success": False, "error": f"Unknown action: {action}"}
                    
                    results.append({"step": step, "result": result})
            
            except Exception as e:
                results.append({"step": step, "error": str(e)})
        
        return results
    
    def get_status(self) -> Dict:
        """Get complete environment status for AI"""
        return {
            "workspace": str(self.workspace_root),
            "terminals": self.terminal.list(),
            "recent_file_ops": self.fs.get_operation_log(last_n=20),
            "project_structure": self.fs.get_tree(max_depth=2)
        }


# ============================================================================
# DEMO / USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("AI DEV MANAGER - Complete Terminal + File System Control")
    print("="*70)
    
    # Initialize manager
    manager = AIDevManager(workspace_root="./test_workspace", terminal_mode="system")
    
    print("\n[1] Creating Python project...")
    result = manager.create_project("my_ai_app", "python")
    print(f"✓ Project created: {result['path']}")
    
    print("\n[2] Listing project structure...")
    tree = manager.fs.get_tree("my_ai_app", max_depth=2)
    print(json.dumps(tree, indent=2))
    
    print("\n[3] Writing custom code file...")
    code = '''def greet(name):
    """Greet someone"""
    return f"Hello, {name}!"

def main():
    print(greet("AI"))

if __name__ == "__main__":
    main()
'''
    manager.fs.write_file("my_ai_app/src/greet.py", code)
    print("✓ Code file created")
    
    print("\n[4] Reading the file back...")
    content = manager.fs.read_file("my_ai_app/src/greet.py")
    print(f"✓ Read {content['size']} characters")
    
    print("\n[5] Executing workflow (terminal + file operations)...")
    workflow = [
        {"type": "terminal", "command": "python --version", "capture": True},
        {"type": "file", "action": "write", "path": "my_ai_app/config.json", 
         "content": json.dumps({"debug": True, "version": "1.0"})},
        {"type": "terminal", "command": "python my_ai_app/src/greet.py", "capture": True}
    ]
    
    results = manager.execute_workflow(workflow)
    for i, result in enumerate(results, 1):
        print(f"\n  Step {i}: {result['step']['type']}")
        if 'result' in result:
            if isinstance(result['result'], dict) and 'output' in result['result']:
                print(f"  Output: {result['result']['output'].strip()}")
    
    print("\n[6] Getting complete status...")
    status = manager.get_status()
    print(f"✓ Workspace: {status['workspace']}")
    print(f"✓ Terminals: {len(status['terminals'])}")
    print(f"✓ Recent file operations: {len(status['recent_file_ops'])}")
    
    print("\n" + "="*70)
    print("✓ COMPLETE! AI now has full control:")
    print("  • Terminal access (create, execute, monitor)")
    print("  • File system access (read, write, modify, delete)")
    print("  • Project creation and workflow execution")
    print("  • Full operation logging for AI decision-making")
    print("="*70)
