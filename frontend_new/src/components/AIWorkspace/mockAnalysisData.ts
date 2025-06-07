import type { AnalysisResult } from '../../types';

export const MOCK_ANALYSIS_RESULTS: AnalysisResult[] = [
  {
    analysisType: 'summary',
    content: `This conversation is a brief, friendly exchange between two speakers who are catching up and transitioning into a project discussion. The dialogue begins with casual greetings and quickly moves to substantive work-related topics.

## Key Discussion Points

• **Project Status:** Speaker 2 indicates that good progress is being made on a previously discussed project
• **Areas of Concern:** Specific areas have been identified that need additional focus and attention  
• **Timeline Challenges:** The current timeline may be too ambitious for the outlined scope
• **Proposed Solutions:** Either adjust the timeline or narrow focus to critical features first

The tone throughout is professional yet collaborative, suggesting these speakers have an established working relationship and are comfortable discussing project challenges openly.`,
    createdAt: new Date(Date.now() - 2 * 60 * 1000).toISOString(), // 2 minutes ago
    status: 'completed',
  },
  {
    analysisType: 'keywords',
    content: `**Primary Keywords:** project, progress, timeline, scope, focus, features

## Key Themes
• Project Management & Planning
• Timeline Optimization  
• Scope Management
• Professional Collaboration
• Strategic Decision Making

## Entities Mentioned
• Previous week's discussion
• Current project
• Critical features

**Action-Oriented Terms:** discuss, focus, adjust, narrow down, outline`,
    createdAt: new Date(Date.now() - 1 * 60 * 1000).toISOString(), // 1 minute ago
    status: 'completed',
  },
  {
    analysisType: 'sentiment',
    content: `**Overall Sentiment:** Positive (Confidence: 87%)
**Dominant Tone:** Professional, Collaborative, Constructive

## Speaker-Level Analysis
• **Speaker 1:** Neutral to Positive - Engaged and responsive, asks clarifying questions
• **Speaker 2:** Positive - Proactive, solution-oriented, transparent about challenges

## Emotional Indicators
• Warmth in initial greetings
• Professional confidence when discussing work
• Constructive problem-solving attitude
• No signs of frustration or conflict

**Conversation Dynamics:** The dialogue demonstrates mutual respect and collaborative problem-solving. Both parties are comfortable discussing challenges, indicating a mature working relationship.`,
    createdAt: new Date(Date.now() - 30 * 1000).toISOString(), // 30 seconds ago
    status: 'completed',
  },
];

export const generateMockAnalysisResult = (analysisType: AnalysisResult['analysisType']): AnalysisResult => {
  const mockContent: Record<AnalysisResult['analysisType'], string> = {
    summary: `# Meeting Summary

This transcript contains a discussion about project management and timeline optimization. The key participants engage in collaborative problem-solving while maintaining a professional and constructive tone throughout the conversation.

## Main Topics Covered
• Project status updates and progress review
• Timeline concerns and potential adjustments
• Scope management and feature prioritization
• Collaborative decision-making process`,

    keywords: `**Core Keywords:** meeting, discussion, project, timeline, management, collaboration, planning

## Thematic Categories
• **Project Management:** planning, coordination, oversight, progress tracking
• **Communication:** discussion, collaboration, feedback, updates
• **Decision Making:** prioritization, assessment, strategy, solutions

## Contextual Terms
• Previous discussions and historical context
• Current project status and ongoing work
• Future planning and strategic direction`,

    sentiment: `**Overall Sentiment Score:** 0.72 (Positive)
**Confidence Level:** 89%

## Emotional Analysis
• **Primary Emotion:** Professional confidence (40%)
• **Secondary Emotion:** Collaborative engagement (35%)
• **Tertiary Emotion:** Constructive concern (25%)

## Tone Characteristics
• **Formality Level:** Professional but approachable
• **Engagement Level:** High mutual engagement
• **Conflict Level:** None detected - purely collaborative`,

    qa: `## Generated Questions & Answers

**Q: What is the main focus of this conversation?**
A: The conversation centers on project management, specifically addressing timeline concerns and the need to adjust either the project scope or timeline to ensure successful completion.

**Q: What challenges are mentioned regarding the current project?**
A: The speakers identify that the current timeline may be too ambitious for the outlined scope, suggesting either timeline adjustment or scope refinement is needed.

**Q: How would you characterize the relationship between the speakers?**
A: The speakers demonstrate a professional, collaborative relationship with mutual respect and comfort in discussing project challenges openly.

**Q: What solutions are proposed for the identified challenges?**
A: Two main solutions are discussed: adjusting the timeline to be more realistic, or narrowing the focus to prioritize the most critical features first.`,

    'action-items': `# Action Items & Next Steps

## Immediate Actions
1. **Timeline Assessment** - Review current project timeline for feasibility
2. **Scope Analysis** - Evaluate project scope against available resources
3. **Priority Mapping** - Identify and rank critical features for initial focus

## Short-term Goals
• Schedule follow-up meeting to discuss timeline adjustments
• Prepare detailed analysis of scope vs. timeline trade-offs
• Develop alternative project roadmap with phased approach

## Long-term Objectives
• Establish more realistic project planning processes
• Improve estimation accuracy for future projects
• Build in buffer time for unforeseen challenges`,

    'topic-detection': `# Topic Analysis & Distribution

## Primary Topics (by discussion time)
1. **Project Timeline Management** (45% of conversation)
   - Timeline feasibility concerns
   - Adjustment strategies and options
   
2. **Scope Management** (30% of conversation)  
   - Feature prioritization discussions
   - Resource allocation considerations

3. **Team Collaboration** (15% of conversation)
   - Working relationship dynamics
   - Communication patterns

4. **Strategic Planning** (10% of conversation)
   - Future project approaches
   - Process improvement opportunities

## Topic Transitions
The conversation flows naturally from casual greetings → status updates → challenge identification → solution brainstorming.`,
  };

  return {
    analysisType,
    content: mockContent[analysisType],
    createdAt: new Date().toISOString(),
    status: 'completed',
  };
};