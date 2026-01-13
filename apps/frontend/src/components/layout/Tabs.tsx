import { ReactNode } from "react";
import { Box, Tabs as MuiTabs, Tab as MuiTab, Chip } from "@mui/material";

interface Tab {
  id: string;
  label: string;
  icon?: ReactNode;
  badge?: number;
}

interface TabsProps {
  tabs: Tab[];
  activeTab: string;
  onChange: (tabId: string) => void;
  className?: string;
}

export const Tabs = ({ tabs, activeTab, onChange, className }: TabsProps) => {
  const activeIndex = tabs.findIndex((tab) => tab.id === activeTab);

  return (
    <Box
      className={className}
      sx={{
        borderBottom: 1,
        borderColor: "divider",
      }}
    >
      <MuiTabs
        value={activeIndex !== -1 ? activeIndex : 0}
        onChange={(_, newValue) => onChange(tabs[newValue].id)}
        aria-label="tabs"
      >
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;

          return (
            <MuiTab
              key={tab.id}
              label={
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  {tab.icon}
                  <span>{tab.label}</span>
                  {tab.badge !== undefined && (
                    <Chip
                      label={tab.badge}
                      size="small"
                      color={isActive ? "primary" : "default"}
                      sx={{ ml: 1, height: 20, minWidth: 20 }}
                    />
                  )}
                </Box>
              }
              sx={{
                textTransform: "none",
                fontWeight: 500,
                fontSize: "0.875rem",
              }}
            />
          );
        })}
      </MuiTabs>
    </Box>
  );
};
