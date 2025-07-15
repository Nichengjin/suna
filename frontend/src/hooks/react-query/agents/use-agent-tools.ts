import { useQuery } from '@tanstack/react-query';
import { createClient } from '@/lib/supabase/client';
import { isFlagEnabled } from '@/lib/feature-flags';

const API_URL = 'https://suna-backend-production-b642.up.railway.app/api';

export interface AgentTool {
  name: string;
  description: string;
  type: 'agentpress' | 'mcp';
  server?: string;
  enabled: boolean;
  icon?: string;
  color?: string;
}

interface AgentToolsResponse {
  agentpress_tools: AgentTool[];
  mcp_tools: AgentTool[];
}

const fetchAgentTools = async (agentId: string): Promise<AgentToolsResponse> => {
  const agentPlaygroundEnabled = await isFlagEnabled('custom_agents');
  if (!agentPlaygroundEnabled) {
    throw new Error('Custom agents is not enabled');
  }

  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();

  if (!session) {
    throw new Error('You must be logged in to get agent tools');
  }

  const response = await fetch(`${API_URL}/agents/${agentId}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session.access_token}`,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
  }

  const agent = await response.json();
  
  // Handle both versioned and non-versioned configurations
  let agentpressToolsConfig, configuredMcps, customMcps;
  
  if (agent.current_version) {
    // Use version data if available
    agentpressToolsConfig = agent.current_version.agentpress_tools || {};
    configuredMcps = agent.current_version.configured_mcps || [];
    customMcps = agent.current_version.custom_mcps || [];
  } else {
    // Fallback to agent data directly (backward compatibility)
    agentpressToolsConfig = agent.agentpress_tools || {};
    configuredMcps = agent.configured_mcps || [];
    customMcps = agent.custom_mcps || [];
  }
  
  const agentpressTools: AgentTool[] = [];
  const defaultTools: Record<string, { description: string; icon: string; color: string }> = {
    'sb_shell_tool': { description: 'Execute shell commands in tmux sessions', icon: '💻', color: 'bg-slate-100' },
    'sb_files_tool': { description: 'Create, read, update, and delete files', icon: '📁', color: 'bg-blue-100' },
    'sb_browser_tool': { description: 'Browser automation and web navigation', icon: '🌐', color: 'bg-indigo-100' },
    'sb_deploy_tool': { description: 'Deploy applications and services', icon: '🚀', color: 'bg-green-100' },
    'sb_expose_tool': { description: 'Expose services and manage ports', icon: '🔌', color: 'bg-orange-100' },
    'web_search_tool': { description: 'Search the web using Tavily API', icon: '🔍', color: 'bg-yellow-100' },
    'sb_vision_tool': { description: 'Vision and image processing capabilities', icon: '👁️', color: 'bg-pink-100' },
    'data_providers_tool': { description: 'Access to data providers and external APIs', icon: '🔗', color: 'bg-cyan-100' },
  };

  for (const [toolName, toolConfig] of Object.entries(agentpressToolsConfig)) {
    const defaultTool = defaultTools[toolName];
    if (defaultTool && toolConfig && typeof toolConfig === 'object' && 'enabled' in toolConfig) {
      agentpressTools.push({
        name: toolName,
        description: defaultTool.description,
        type: 'agentpress',
        enabled: Boolean(toolConfig.enabled),
        icon: defaultTool.icon,
        color: defaultTool.color,
      });
    }
  }

  const mcpTools: AgentTool[] = [];
  
  for (const mcpConfig of configuredMcps) {
    if (mcpConfig.enabledTools && Array.isArray(mcpConfig.enabledTools)) {
      for (const toolName of mcpConfig.enabledTools) {
        mcpTools.push({
          name: toolName,
          description: `${toolName} from ${mcpConfig.name}`,
          type: 'mcp',
          server: mcpConfig.name,
          enabled: true,
          icon: '🔧',
          color: 'bg-purple-100',
        });
      }
    }
  }

  for (const customMcp of customMcps) {
    if (customMcp.enabledTools && Array.isArray(customMcp.enabledTools)) {
      for (const toolName of customMcp.enabledTools) {
        const customType = customMcp.customType || customMcp.type || 'sse';
        mcpTools.push({
          name: toolName,
          description: `${toolName} from ${customMcp.name} (${customType})`,
          type: 'mcp',
          server: customMcp.name,
          enabled: true,
          icon: customType === 'sse' ? '🌐' : customType === 'http' ? '📡' : '⚙️',
          color: 'bg-indigo-100',
        });
      }
    }
  }

  return {
    agentpress_tools: agentpressTools,
    mcp_tools: mcpTools,
  };
};

export const useAgentTools = (agentId: string) => {
  return useQuery({
    queryKey: ['agent-tools', agentId],
    queryFn: () => fetchAgentTools(agentId),
    staleTime: 5 * 60 * 1000,
    enabled: !!agentId,
  });
}; 