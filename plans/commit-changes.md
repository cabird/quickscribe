# Create Git Commit with AI-Generated Message

## Overview
This plan guides through the process of staging tracked files, analyzing changes, generating an appropriate commit message, and creating the commit after user confirmation.

## Prerequisites
- Git repository initialized
- Working directory has modified files
- Git credentials configured if needed
- Working from repository root directory

## Implementation Steps

### 1. Stage Modified Tracked Files
1. From repository root, run `git add -u` to stage all modified tracked files
   - This only stages files already in git, not untracked files
   - Preserves the user's choice about which new files to include

### 2. Verify Staging Status
1. Run `git status` to confirm files were staged correctly
2. Review the list of:
   - Files staged for commit (green)
   - Untracked files not staged (red)

### 3. Analyze Staged Changes
1. Get overview of changes: `git diff --cached --stat`
   - Shows file change summary with line counts
   - Helps understand scope of changes
2. For deeper analysis, examine specific files:
   - List changed files: `git diff --cached --name-only | head -10`
   - Check new files: `git diff --cached <new-file> | head -50`
   - Check modified files: `git diff --cached <modified-file> | head -80`

### 4. Generate Commit Message
1. Analyze the changes to identify:
   - What type of changes (feature, fix, refactor, etc.)
   - Which components were affected
   - The purpose and impact of changes
2. Structure the commit message:
   - First line: Concise summary (50-72 chars)
   - Blank line
   - Detailed explanation of major changes
   - List key modifications
   - Explain the why, not just the what

### 5. Present Message for Approval
1. Show the complete commit message to the user
2. Wait for explicit confirmation before proceeding
3. Allow user to request modifications if needed

### 6. Create the Commit
1. Use heredoc syntax to preserve formatting:
   ```bash
   git commit -m "$(cat <<'EOF'
   [Commit message here]
   EOF
   )"
   ```
2. Verify commit succeeded with exit code

### 7. Confirm Final Status
1. Run `git status` to show:
   - Clean working directory (if all changes committed)
   - Remaining untracked files
   - Branch ahead/behind status

## Error Handling
- If `git add -u` fails: Check if in git repository
- If no changes staged: Inform user there's nothing to commit
- If commit fails: Check for pre-commit hooks or other issues

## Best Practices
- Always analyze changes thoroughly before generating message
- Keep first line of commit message concise and descriptive
- Include enough detail for future developers to understand the changes
- Use present tense ("Add feature" not "Added feature")
- Group related changes in the commit message
- Mention breaking changes prominently

## Example Execution
```bash
# From repository root
cd /path/to/repository

# Stage changes
git add -u

# Check what was staged  
git status

# Analyze changes
git diff --cached --stat

# After generating and confirming message
git commit -m "$(cat <<'EOF'
Implement dynamic analysis types system

- Add backend CRUD operations for analysis types
- Create modular frontend components  
- Update shared models and documentation
EOF
)"
```