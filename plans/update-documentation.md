# Documentation Update Plan

This plan describes how to systematically update all project documentation based on git commit history since the last documented state.

## Overview

The project maintains several types of documentation that need periodic updates:
- Root-level directory mapping file
- Architecture document (root level)
- Component README files (in each subdirectory)
- Component architecture files (in each subdirectory)

Each documentation file tracks the last commit it was updated for, allowing incremental updates based only on changes since that point.

## Step-by-Step Process

### 1. Identify Documentation Files

Scan the project for documentation files that need updating:
- Look for files named: `directory-mapping.*`, `architecture.*`, `README.*`, `readme.*`
- Check both root directory and all subdirectories
- Create a list of all documentation files found

### 2. Check Current Documentation State

For each documentation file found:
- Look for a metadata section that indicates the last documented commit
- The format should be one of:
  ```
  <!-- Last updated for commit: [COMMIT_HASH] -->
  ```
  or
  ```yaml
  ---
  last_documented_commit: [COMMIT_HASH]
  ---
  ```
- If no commit hash is found, treat it as never documented (start from first commit)

### 3. Analyze Changes Since Last Update

For each documentation file:
- Run `git log --oneline [LAST_COMMIT_HASH]..HEAD` to get commits since last update
- If this is the first documentation, use `git log --oneline` for all commits
- For each commit in the range, run `git show --name-only [COMMIT_HASH]` to see changed files
- Identify which changes are relevant to the documentation being updated:
  - For root architecture: any structural changes, new components, removed components
  - For directory mapping: new directories, removed directories, changed purposes
  - For component README: changes within that specific subdirectory
  - For component architecture: changes to that component's internal structure

### 4. Gather Change Context

For relevant commits:
- Read the commit messages to understand the intent of changes
- Use `git diff [COMMIT_HASH]~1 [COMMIT_HASH]` to see the actual changes
- Note any new files, deleted files, or significant structural modifications
- Pay special attention to:
  - New directories or components
  - Deleted directories or components  
  - Changes to file organization
  - New dependencies or architectural patterns

### 5. Update Each Documentation File

For each documentation file that needs updates:

#### Read Current Content
- Read the entire current documentation file
- Understand its current structure and content

#### Identify Required Updates
- Based on the changes found, determine what sections need modification
- Look for:
  - Outdated directory descriptions
  - Missing new components
  - References to deleted components
  - Outdated architectural descriptions
  - New patterns or approaches that should be documented

#### Update Content
- Modify the documentation to reflect current state
- Maintain the existing tone and structure
- Add new sections for new components/directories
- Remove or update sections for changed/deleted items
- Ensure consistency with the actual current codebase

#### Update Metadata
- Get the latest commit hash with `git rev-parse HEAD`
- Update the metadata section with the new commit hash:
  ```
  <!-- Last updated for commit: [NEW_COMMIT_HASH] -->
  ```

### 6. Verification

After updating all documentation:
- Review each updated file to ensure accuracy
- Check that all new components/directories are documented
- Verify that no outdated information remains
- Ensure all commit metadata is properly updated

## Special Considerations

### Component-Specific Updates
- Component READMEs should focus on changes within their specific directory
- Component architecture files should detail internal structural changes
- Don't update component docs for changes that happened elsewhere

### Root-Level Updates  
- Root architecture should capture high-level structural changes
- Directory mapping should reflect any new/changed/removed directories
- Focus on the overall system organization

### Commit Message Analysis
- Pay attention to commit messages that indicate architectural changes
- Messages like "refactor", "restructure", "add component", "remove" are key
- Messages about bug fixes or minor tweaks may not require doc updates

### Preserving Documentation Quality
- Maintain the existing writing style and level of detail
- Don't just append new information - integrate it properly
- Keep documentation concise but comprehensive

## Success Criteria

The documentation update is complete when:
- All documentation files have current commit hashes in their metadata
- All new components, directories, and architectural changes are documented
- No outdated information remains in any documentation file
- The documentation accurately reflects the current state of the codebase

## Final Step: Commit Confirmation

After completing all documentation updates:

1. **Present Summary to User**
   - Provide a clear summary of all files that were updated
   - List the key changes made to each documentation file
   - Show which new features, directories, or architectural changes were documented
   - Confirm that commit metadata has been added to all appropriate files

2. **Request Commit Confirmation**
   - Ask the user if they want to commit the documentation changes
   - Explain that this will create a commit with all the updated documentation
   - Wait for explicit user confirmation before proceeding

3. **If User Confirms**
   - Stage all modified documentation files
   - Create a commit with an appropriate message (e.g., "Update comprehensive project documentation with latest features and architecture")
   - Include the standard AI-generated commit footer

4. **If User Declines**
   - Leave the changes unstaged for the user to review and commit manually
   - Inform them that the documentation updates are complete but not yet committed
