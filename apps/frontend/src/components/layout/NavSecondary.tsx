import { LucideIcon } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import {
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  SxProps,
  Theme,
} from "@mui/material";

interface NavSecondaryProps {
  items: {
    title: string;
    url: string;
    icon: LucideIcon;
  }[];
  sx?: SxProps<Theme>;
}

export function NavSecondary({ items, sx }: NavSecondaryProps) {
  const location = useLocation();

  return (
    <List sx={{ px: 1.5, ...sx }}>
      {items.map((item) => {
        const isActive = location.pathname === item.url;
        const Icon = item.icon;

        return (
          <ListItem key={item.title} disablePadding sx={{ mb: 0.5 }}>
            <ListItemButton
              component={Link}
              to={item.url}
              selected={isActive}
              sx={{
                borderRadius: 1,
                "&.Mui-selected": {
                  bgcolor: "action.selected",
                  "&:hover": {
                    bgcolor: "action.selected",
                  },
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 40 }}>
                <Icon size={16} />
              </ListItemIcon>
              <ListItemText primary={item.title} />
            </ListItemButton>
          </ListItem>
        );
      })}
    </List>
  );
}
