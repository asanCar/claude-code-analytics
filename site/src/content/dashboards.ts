export type Dashboard = {
  slug: string;
  title: string;
  audience: 'overview' | 'cost' | 'model' | 'workflow' | 'detail';
  question: string;
  description: string;
  panels: string[];
  featured: boolean;
  media?: {
    poster: string;
    webm?: string;
    mp4?: string;
  };
  jsonPath: string;
};

const mediaFor = (slug: string, base: string) => ({
  poster: `${base}/dashboards/${slug}.png`,
  webm:   `${base}/dashboards/${slug}.webm`,
  mp4:    `${base}/dashboards/${slug}.mp4`,
});

const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

export const dashboards: Dashboard[] = [
  {
    slug: 'summary',
    title: 'Summary',
    audience: 'overview',
    question: "What's the high-level state of my Claude Code usage?",
    description:
      "The big picture in one screen. Plan utilization for the 5-hour and 7-day windows, weekly token totals, daily activity, top projects, and the work-mix breakdown — designed for a quick glance, no Grafana experience required.",
    panels: [
      'Current Plan',
      'Plan utilization (5h)',
      'Plan utilization (7d)',
      'Tokens this week',
      'Daily Claude activity',
      'Top projects by tokens',
      'Work mix per week (%)',
    ],
    featured: true,
    media: mediaFor('summary', BASE),
    jsonPath: 'grafana/dashboards-summary/summary.json',
  },
  {
    slug: 'model-usage',
    title: 'Model Usage',
    audience: 'model',
    question: 'Which models am I using, and where?',
    description:
      "Splits token volume across Claude models, tracks how that split shifts over time, breaks it down per project, and separates main-thread usage from subagent traffic.",
    panels: [
      'Token Split by Model',
      'Model Usage Over Time',
      'Model Per Project',
      'Subagent vs Main',
    ],
    featured: true,
    media: { poster: `${BASE}/dashboards/model-usage.png` },
    jsonPath: 'grafana/dashboards/model-usage.json',
  },
  {
    slug: 'per-project',
    title: 'Per-Project Breakdown',
    audience: 'workflow',
    question: 'Which repos consume the most tokens?',
    description:
      "Token consumption ranked by project, with activity over time, the mix of tools used in each repo, the archetype mix, and session counts. Useful for spotting which workspaces are driving your usage.",
    panels: [
      'Token Consumption by Project',
      'Project Activity Over Time',
      'Tool Mix by Project',
      'Archetype Mix by Project (%)',
      'Sessions Per Project',
    ],
    featured: true,
    media: mediaFor('per-project', BASE),
    jsonPath: 'grafana/dashboards/per-project.json',
  },
  {
    slug: 'per-session',
    title: 'Per-Session Detail',
    audience: 'detail',
    question: 'What happened inside one specific session?',
    description:
      "Drill into one session: the full prompt history, message-type breakdown, token totals across input/output/cache-read, the timeline, and the archetype mix. Click a session row to filter the rest of the dashboard.",
    panels: [
      'Sessions (click a session_id to filter)',
      'Prompt History',
      'Total Input Tokens',
      'Total Output Tokens',
      'Total Cache Read Tokens',
      'Message Count',
      'Session Timeline',
      'Archetype Mix (%)',
    ],
    featured: true,
    media: mediaFor('per-session', BASE),
    jsonPath: 'grafana/dashboards/per-session.json',
  },
  {
    slug: 'prompt-cost',
    title: 'Prompt Cost Ranking',
    audience: 'cost',
    question: 'Which prompts and tools are the most expensive?',
    description:
      "A leaderboard view: most expensive prompts, most expensive sessions, top tools by cost, and average tokens per message and per tool over time. The sharp end of the cost question.",
    panels: [
      'Most Expensive Prompts',
      'Most Expensive Sessions',
      'Top 10 Most Expensive Tools',
      'Avg Tokens: assistant_text',
      'Avg Tokens: tool_use',
      'Average Tokens per Message Over Time',
      'Average Tokens per Tool Over Time',
    ],
    featured: true,
    media: mediaFor('prompt-cost', BASE),
    jsonPath: 'grafana/dashboards/prompt-cost.json',
  },

  {
    slug: 'token-utilization',
    title: 'Token Utilization',
    audience: 'overview',
    question: 'How fast am I burning my plan budget?',
    description:
      "Tokens over time alongside plan utilization trend and a count of daily active sessions. The 'am I going to run out' view.",
    panels: ['Tokens Over Time', 'Daily Active Sessions', 'Usage Utilization Trend'],
    featured: false,
    jsonPath: 'grafana/dashboards/token-utilization.json',
  },
  {
    slug: 'cache-efficiency',
    title: 'Cache Efficiency',
    audience: 'cost',
    question: 'Is the prompt cache actually paying off?',
    description:
      "Cache hit ratio over time, the read-vs-fresh-input balance, daily cache creation tokens, and which projects benefit most from caching.",
    panels: [
      'Cache Hit Ratio Over Time',
      'Cache Read vs Fresh Input',
      'Cache Creation Tokens Per Day',
      'Most Cache-Efficient Projects',
    ],
    featured: false,
    jsonPath: 'grafana/dashboards/cache-efficiency.json',
  },
  {
    slug: 'consumption-ratio',
    title: 'Consumption Ratio',
    audience: 'cost',
    question: 'How many tokens does each 1% of plan utilization cost?',
    description:
      "Tokens per 1% utilization across both the 5-hour and 7-day windows, plotted alongside the utilization line and an estimated absolute budget.",
    panels: [
      'Tokens per 1% Utilization (5-hour window)',
      'Tokens per 1% Utilization (7-day window)',
      'Token Consumption vs 5-hour Utilization',
      'Token Consumption vs 7-day Utilization',
      'Estimated 5h Budget (tokens)',
      'Estimated 7d Budget (tokens)',
    ],
    featured: false,
    jsonPath: 'grafana/dashboards/consumption-ratio.json',
  },
  {
    slug: 'weekly-workflow',
    title: 'Weekly Workflow Trends',
    audience: 'workflow',
    question: 'How is my work changing week over week?',
    description:
      "This week vs last week vs the 4-week average, broken down by tool tokens, category mix (absolute and percentage), dominant archetype per session, and average tokens per message by archetype.",
    panels: [
      'This Week (tool tokens)',
      'Last Week (tool tokens)',
      'WoW Change',
      '4-Week Avg (tool tokens)',
      'Tool Tokens per Week',
      'Category Mix per Week (absolute)',
      'Category Mix per Week (%)',
      'Sessions per Dominant Archetype per Week',
      'Avg Tokens per Message by Archetype',
    ],
    featured: false,
    jsonPath: 'grafana/dashboards/weekly-workflow.json',
  },
];

export const featuredDashboards = dashboards.filter((d) => d.featured);
export const otherDashboards   = dashboards.filter((d) => !d.featured);
