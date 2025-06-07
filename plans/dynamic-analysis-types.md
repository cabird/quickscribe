# Dynamic Analysis Types Implementation Plan

## Overview

Transform the QuickScribe AI workspace from a static, hardcoded analysis tool set into a fully dynamic, data-driven platform where analysis types are stored in CosmosDB and completely customizable by users.

### How It Works

**Current System**: The AI workspace has 6 hardcoded analysis types (Summary, Keywords, Q&A, Sentiment, Action Items, Topic Detection) defined in multiple frontend components. Adding a new analysis requires code changes across multiple files.

**New System**: Analysis types become database records that define:
- **Display Properties**: Title, description, icon selection
- **LLM Behavior**: Custom prompts that control how AI analyzes transcripts
- **User Ownership**: Global (built-in) types vs user-created custom types

**Data-Driven UI Generation**: The frontend fetches available analysis types on app load and dynamically generates:
- Tool buttons in the analysis workspace
- Tab labels for completed analyses  
- Icon rendering from a predefined library
- Analysis execution with custom prompts

**User Creation Workflow**: Users can create custom analysis types through a management interface:
1. Enter title and description for their custom analysis
2. Select an icon from a curated library of 50+ options
3. Write a custom LLM prompt that defines how the analysis works
4. Save and immediately use their custom analysis on any transcript

**Example Custom Analysis**: A user could create "Meeting Action Items" with the prompt: "Extract all action items, decisions, and commitments from this meeting transcript. List the responsible person and deadline for each item where mentioned."

This transforms QuickScribe from a fixed-function tool into a customizable AI analysis platform where users can build their own specialized analysis workflows without any code changes.

## Current State

### Frontend (frontend_new/)
- Analysis types hardcoded as TypeScript union: `'summary' | 'keywords' | 'sentiment' | 'qa' | 'action-items' | 'topic-detection'`
- Analysis tools defined in multiple components:
  - `src/components/AIWorkspace/ToolsTab.tsx` - ANALYSIS_TOOLS array with icons/descriptions
  - `src/components/AIWorkspace/TabNavigation.tsx` - TAB_LABELS record
  - `src/components/AIWorkspace/ResultsOverviewTab.tsx` - ANALYSIS_LABELS record
  - `src/components/AIWorkspace/ResultTab.tsx` - ANALYSIS_LABELS record
  - `src/components/AIWorkspace/mockAnalysisData.ts` - Mock content

### Backend
- No analysis types system exists
- No AI analysis execution endpoints
- Analysis results stored in `Transcription.analysisResults` array

### Shared Models
- `AnalysisResult` interface with hardcoded `analysisType` enum in `shared/Models.ts`

## Target Architecture

### Data Model

**New CosmosDB Container: `analysis_types`**
```typescript
interface AnalysisType {
  id: string;                    // Unique identifier (UUID)
  name: string;                  // Internal identifier (slug-like: "custom-meeting-summary")
  title: string;                 // Display name ("Custom Meeting Summary")
  description: string;           // User-facing description
  icon: string;                  // Icon identifier from predefined library
  prompt: string;                // LLM prompt template with placeholders
  userId?: string;               // null for global types, userId for custom types
  isActive: boolean;             // Admin can disable types
  isBuiltIn: boolean;            // True for system defaults, false for user-created
  createdAt: string;             // ISO timestamp
  updatedAt: string;             // ISO timestamp
  partitionKey: string;          // userId for custom, "global" for built-in
}
```

**Updated AnalysisResult interface:**
```typescript
interface AnalysisResult {
  analysisType: string;          // Changed from enum to string (references AnalysisType.name)
  analysisTypeId: string;        // References AnalysisType.id
  content: string;
  createdAt: string;
  status: 'pending' | 'completed' | 'failed';
  errorMessage?: string;
}
```

### API Endpoints

**New endpoints in `backend/routes/ai_routes.py` (existing AI blueprint):**

1. `GET /api/ai/analysis-types`
   - Returns available analysis types for current user
   - Includes global (built-in) types + user's custom types
   - Response: `AnalysisType[]`

2. `POST /api/ai/analysis-types`
   - Create custom analysis type
   - Body: `{ name, title, description, icon, prompt }`
   - Validates uniqueness of name per user
   - Returns created `AnalysisType`

3. `PUT /api/ai/analysis-types/{id}`
   - Update custom analysis type (user can only edit their own)
   - Body: partial `AnalysisType`
   - Returns updated `AnalysisType`

4. `DELETE /api/ai/analysis-types/{id}`
   - Delete custom analysis type (user can only delete their own)
   - Cannot delete built-in types
   - Returns success status

5. `POST /api/ai/execute-analysis`
   - Execute analysis with dynamic type and prompt
   - Body: `{ transcriptionId, analysisTypeId, customPrompt? }`
   - Uses analysisType.prompt or customPrompt override
   - Returns success status (analysis runs async)

### Database Handlers

**New handler: `backend/db_handlers/analysis_type_handler.py`**
```python
class AnalysisTypeHandler:
    def get_analysis_types_for_user(self, user_id: str) -> List[AnalysisType]
    def create_analysis_type(self, analysis_type: AnalysisType) -> AnalysisType
    def update_analysis_type(self, type_id: str, updates: dict) -> AnalysisType
    def delete_analysis_type(self, type_id: str) -> bool
    def get_analysis_type_by_id(self, type_id: str) -> AnalysisType
    def get_built_in_analysis_types(self) -> List[AnalysisType]
```

## Implementation Plan

### Phase 1: Backend Foundation

#### 1.1 Database Structure
- [ ] Create `analysis_types` container in CosmosDB
- [ ] Update `shared/Models.ts` with new interfaces
- [ ] Run `make build` to generate Python models

#### 1.2 Database Handler
- [ ] Create `backend/db_handlers/analysis_type_handler.py`
- [ ] Add to `handler_factory.py`
- [ ] Implement all CRUD operations
- [ ] Add proper error handling and validation

#### 1.3 Seed Data
- [ ] Create script to populate built-in analysis types:
  ```python
  # Built-in analysis types with their prompts
  BUILT_IN_TYPES = [
    {
      "name": "summary",
      "title": "Generate Summary", 
      "description": "Create a concise overview of the main topics and key points",
      "icon": "file-text",
      "prompt": "Please provide a concise summary of the following transcript, highlighting the main topics and key points discussed:\n\n{transcript}"
    },
    # ... other 5 built-in types
  ]
  ```

#### 1.4 API Endpoints
- [ ] Implement all 5 API endpoints in `backend/routes/ai_routes.py`
- [ ] Add authentication checks
- [ ] Add input validation
- [ ] Add error handling
- [ ] Test endpoints with proper user context

### Phase 2: Frontend Dynamic Loading

#### 2.1 Store Updates
- [ ] Add analysis types to `useUIStore` or create new `useAnalysisStore`
- [ ] Add actions: `loadAnalysisTypes()`, `addAnalysisType()`, etc.
- [ ] Fetch analysis types on app load in `App.tsx`

#### 2.2 Icon Library
- [ ] Create `src/constants/iconLibrary.ts` with 50-100 Lucide icons
- [ ] Create `IconRenderer` component that maps string → React component
- [ ] Use type-safe approach: `type IconName = keyof typeof ICON_LIBRARY`

#### 2.3 Component Updates
- [ ] Update `ToolsTab.tsx` to use dynamic analysis types from store
- [ ] Update `TabNavigation.tsx` to use dynamic labels
- [ ] Update `ResultsOverviewTab.tsx` and `ResultTab.tsx` for dynamic types
- [ ] Remove hardcoded `ANALYSIS_TOOLS`, `TAB_LABELS`, `ANALYSIS_LABELS`

#### 2.4 Backward Compatibility
- [ ] Keep mock data as fallback during development
- [ ] Ensure graceful degradation if API fails
- [ ] Test with both hardcoded and dynamic data

### Phase 3: Analysis Execution

#### 3.1 Backend AI Integration
- [ ] Create unified analysis execution service
- [ ] Replace individual analysis logic with prompt-based system
- [ ] Integrate with existing LLM service (OpenAI/Azure)
- [ ] Handle dynamic prompts with transcript injection

#### 3.2 Frontend Execution Updates
- [ ] Update `handleRunAnalysis` to use new API endpoint
- [ ] Pass `analysisTypeId` instead of hardcoded type
- [ ] Handle dynamic analysis type references in results

### Phase 4: User Management UI

#### 4.1 Analysis Type Management
- [ ] Create `AnalysisTypeManager.tsx` component
- [ ] Add to Settings tab or new management modal
- [ ] CRUD interface for custom analysis types
- [ ] Icon picker component using icon library

#### 4.2 Enhanced Workspace
- [ ] Add "Create Custom Analysis" option to workspace
- [ ] Allow users to run custom prompts on demand
- [ ] Save successful custom prompts as new analysis types

## Technical Considerations

### Migration Strategy
1. **Gradual Migration**: Keep hardcoded types as fallback during transition
2. **Database Seeding**: Populate built-in types before frontend deployment
3. **API Versioning**: Consider v2 endpoints if existing analysis logic exists
4. **Testing**: Thorough testing with both built-in and custom analysis types

### Performance
- **Client-side Caching**: Analysis types cached in store, loaded once per session
- **Database Optimization**: Partition by userId for efficient queries
- **Icon Bundle**: Only include used icons to minimize bundle size

### Error Handling
- **Graceful Degradation**: If analysis types fail to load, show basic interface
- **Validation**: Strong validation on analysis type creation (name uniqueness, prompt length)
- **User Feedback**: Clear error messages for failed operations

### Security
- **User Isolation**: Users can only modify their own custom analysis types
- **Prompt Validation**: Basic validation on prompt content (length, format)
- **Built-in Protection**: Cannot delete or modify built-in analysis types

## Success Criteria

### Functional Requirements
- [ ] Users can view all available analysis types (built-in + custom)
- [ ] Users can create custom analysis types with name, description, icon, prompt
- [ ] Users can execute any analysis type on transcriptions
- [ ] Analysis results reference dynamic analysis types correctly
- [ ] Built-in analysis types work identically to current hardcoded system

### Technical Requirements
- [ ] Zero breaking changes to existing analysis result storage
- [ ] Performance equivalent to current hardcoded system
- [ ] Proper error handling and user feedback
- [ ] Type safety maintained where possible (dynamic parts properly typed as strings)

### User Experience
- [ ] Seamless transition - users don't notice the change to built-in analyses
- [ ] Intuitive UI for creating custom analysis types
- [ ] Clear distinction between built-in and custom analysis types
- [ ] Responsive and performant analysis type loading

## Files to Modify

### Backend
- `shared/Models.ts` - Update interfaces
- `backend/db_handlers/analysis_type_handler.py` - New handler
- `backend/db_handlers/handler_factory.py` - Add new handler
- `backend/routes/ai_routes.py` - New endpoints
- `backend/db_handlers/models.py` - Generated from shared models

### Frontend
- `src/stores/useUIStore.ts` or new `useAnalysisStore.ts` - Analysis types state
- `src/components/AIWorkspace/ToolsTab.tsx` - Dynamic tool rendering
- `src/components/AIWorkspace/TabNavigation.tsx` - Dynamic tab labels
- `src/components/AIWorkspace/ResultsOverviewTab.tsx` - Dynamic result labels
- `src/components/AIWorkspace/ResultTab.tsx` - Dynamic result labels
- `src/components/AIWorkspace/AIWorkspaceModal.tsx` - Updated execution logic
- `src/constants/iconLibrary.ts` - New icon library
- `src/components/IconRenderer.tsx` - New icon component
- `src/App.tsx` - Load analysis types on startup

### New Files
- `backend/db_handlers/analysis_type_handler.py`
- `src/constants/iconLibrary.ts`
- `src/components/IconRenderer.tsx`
- `src/components/AnalysisTypeManager.tsx` (Phase 4)

This plan transforms QuickScribe from a static analysis tool into a flexible, user-customizable AI analysis platform while maintaining backward compatibility and performance.