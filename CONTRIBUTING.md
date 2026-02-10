# Contributing to solaredge2mqtt

## Development Setup

This project supports two development workflows:

### 🎯 Standard Workflow (Recommended for Contributors)

This is the standard way to contribute to the project.

1. **Clone the repository:**
   ```bash
   git clone git@github.com:DerOetzi/solaredge2mqtt.git
   cd solaredge2mqtt
   ```

2. **Open in VS Code:**
   ```bash
   code .
   ```

3. **Reopen in devcontainer:**
   - Press `F1` → "Dev Containers: Reopen in Container"
   - Use the default `.devcontainer/devcontainer.json`

4. **Create feature branches as usual:**
   ```bash
   git checkout -b feature-xyz
   ```

---

### 🔧 Worktree Workflow (For Maintainers)

This workflow is designed for maintainers who work on multiple branches simultaneously.

#### Initial Setup

This workflow uses the `manage-worktrees.sh` helper script that automates the entire worktree setup and management process.

**Step 1: Download the helper script**

```bash
curl -O https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/main/scripts/manage-worktrees.sh
chmod +x manage-worktrees.sh
```

**Step 2: Run setup**

```bash
./manage-worktrees.sh setup ~/projects/solaredge2mqtt
```

This single command will:
- Create the directory structure
- Clone the repository as bare
- Set up the main worktree
- Create a shared `config/` directory with example configuration files
- Install the script in your project root for easy access

**Step 3: Configure your settings**

```bash
cd ~/projects/solaredge2mqtt
nano config/configuration.yml  # Edit with your settings
nano config/secrets.yml         # Add your credentials
```

#### Directory Structure

After setup, your project structure looks like this:

```
~/projects/solaredge2mqtt/
├── .repo/                    # Bare repository (git data only)
│   ├── .git/
│   │   └── worktrees/        # Worktree metadata
│   └── ...
├── config/                   # Shared configuration
│   ├── configuration.yml     # Main settings
│   └── secrets.yml           # Credentials
├── manage-worktrees.sh       # Helper script (symlinked)
├── main/                     # Worktree for main branch
│   ├── .devcontainer/
│   ├── .git                  # File pointing to .repo/.git/worktrees/main
│   └── ...
```

#### Opening a Worktree in VS Code

1. **Open the worktree directory:**
   ```bash
   code ~/projects/solaredge2mqtt/main
   ```

2. **Reopen in devcontainer:**
   - Press `F1` → "Dev Containers: Reopen in Container"
   - **Important:** Select `.devcontainer/worktree/devcontainer.json` (not the default one!)

3. **Work normally:**
   - All git commands work as expected
   - The devcontainer automatically fixes worktree paths on startup
   - Configuration files in `../config/` are shared across all worktrees you can use them by executing 
     `ln -s ../config .` in the workspace directory.

#### Creating New Worktrees

**For a new or existing branch:**

```bash
cd ~/projects/solaredge2mqtt
./manage-worktrees.sh add feature-xyz
```

The script automatically:
- Checks if the branch exists locally or remotely
- Creates tracking branches for remote branches
- Creates new branches if they don't exist
- Uses relative paths for portability

**For reviewing a Pull Request:**

```bash
./manage-worktrees.sh add-pr 298
```

This creates a `pr-298/` worktree with the PR's code, ready to review.

**Custom worktree name:**

```bash
./manage-worktrees.sh add feature/complex-name simple-name
```

#### Removing Worktrees

```bash
cd ~/projects/solaredge2mqtt
./manage-worktrees.sh remove feature-xyz
```

This safely removes the worktree and cleans up git metadata.

#### Managing Your Worktrees

**List all active worktrees:**

```bash
./manage-worktrees.sh list
```

**List available remote branches:**

```bash
./manage-worktrees.sh list-remote
```

**Fetch latest updates:**

```bash
./manage-worktrees.sh fetch
```

**Clean up stale worktree entries:**

```bash
./manage-worktrees.sh prune
```

**Get help:**

```bash
./manage-worktrees.sh help
```

---

## Comparison: Standard vs Worktree Workflow

| Aspect | Standard Workflow | Worktree Workflow |
|--------|------------------|-------------------|
| **Target Users** | Contributors | Maintainers |
| **Setup Complexity** | Simple (`git clone`) | More complex (bare repo + worktrees) |
| **Multiple Branches** | Switch with `git checkout` | Open multiple directories simultaneously |
| **Disk Space** | One working copy | Multiple working copies + shared git data |
| **Devcontainer Config** | `.devcontainer/devcontainer.json` | `.devcontainer/worktree/devcontainer.json` |
| **Parent Directory Mount** | No (secure) | Yes (necessary for worktree access) |

---

## Important Notes

- ✅ Both workflows work with the same codebase
- ✅ The worktree structure is **completely optional** - standard workflow continues to work unchanged
- ✅ Contributors don't need to know about worktrees
- ⚠️ When using worktrees, **always select the worktree devcontainer config** when reopening in container
- ⚠️ Do not commit `.repo/` directory - it's for local development only (add to `.gitignore` if needed)
- 📁 The structure inside `solaredge2mqtt/` is standardized: `.repo/` for git data, branch names as worktree directories

---

## Troubleshooting

### Git doesn't work in worktree container

**Symptom:** `fatal: not a git repository` in devcontainer

**Solution:** Make sure you:
1. Selected `.devcontainer/worktree/devcontainer.json` when reopening
2. The parent directory `solaredge2mqtt/` contains both `.repo/` and your worktree

### Wrong devcontainer opened

**Symptom:** Container name is wrong or git doesn't work

**Solution:** 
1. Close VS Code
2. Reopen: `code ~/projects/solaredge2mqtt/main`
3. Press `F1` → "Dev Containers: Reopen in Container"
4. Select `.devcontainer/worktree/devcontainer.json` explicitly

### Want to switch from standard to worktree

**Solution:**
```bash
# 1. Backup your current work
cd ~/existing/solaredge2mqtt
git stash

# 2. Setup new structure
mkdir -p ~/projects/solaredge2mqtt/.repo
cd ~/projects/solaredge2mqtt/.repo
git clone --bare git@github.com:DerOetzi/solaredge2mqtt.git .

# 3. Create worktrees
git worktree add ../main main

# 4. Copy your stashed work
cd ~/projects/solaredge2mqtt/main
git stash pop
```