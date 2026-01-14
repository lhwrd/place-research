import {
  Home,
  Search,
  Heart,
  Settings,
  HelpCircle,
  Building2,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  Box,
  Drawer,
  ListItemButton,
  ListItemIcon,
  Typography,
} from "@mui/material";
import { NavMain } from "./NavMain";
import { NavSecondary } from "./NavSecondary";
import { NavUser } from "./NavUser";
import { useAuth } from "@/hooks/useAuth";

interface AppSidebarProps {
  mobileOpen: boolean;
  onDrawerToggle: () => void;
  drawerWidth: number;
}

export function AppSidebar({
  mobileOpen,
  onDrawerToggle,
  drawerWidth,
}: AppSidebarProps) {
  const { user } = useAuth();

  const navMain = [
    {
      title: "Home",
      url: "/",
      icon: Home,
    },
    {
      title: "Search Properties",
      url: "/search",
      icon: Search,
    },
    {
      title: "Saved Properties",
      url: "/saved",
      icon: Heart,
    },
  ];

  const navSecondary = [
    {
      title: "Preferences",
      url: "/preferences",
      icon: Settings,
    },
    {
      title: "Get Help",
      url: "#",
      icon: HelpCircle,
    },
  ];

  const userInfo = {
    name: user?.full_name || user?.email || "Guest User",
    email: user?.email || "guest@example.com",
    avatar: "",
  };

  const drawerContent = (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <Box sx={{ p: 2 }}>
        <ListItemButton
          component={Link}
          to="/"
          sx={{
            borderRadius: 1,
            "&:hover": { bgcolor: "action.hover" },
          }}
        >
          <ListItemIcon sx={{ minWidth: 40 }}>
            <Box
              sx={{
                width: 32,
                height: 32,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 1,
                bgcolor: "primary.main",
                color: "primary.contrastText",
              }}
            >
              <Building2 size={16} />
            </Box>
          </ListItemIcon>
          <Box>
            <Typography variant="body1" fontWeight="600">
              Place Research
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Property Intelligence
            </Typography>
          </Box>
        </ListItemButton>
      </Box>

      {/* Main Navigation */}
      <Box sx={{ flexGrow: 1, overflowY: "auto" }}>
        <NavMain items={navMain} />
        <NavSecondary items={navSecondary} sx={{ mt: "auto" }} />
      </Box>

      {/* Footer */}
      <Box sx={{ borderTop: 1, borderColor: "divider" }}>
        <NavUser user={userInfo} />
      </Box>
    </Box>
  );

  return (
    <Box
      component="nav"
      sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
    >
      {/* Mobile drawer */}
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onDrawerToggle}
        ModalProps={{
          keepMounted: true, // Better mobile performance
        }}
        sx={{
          display: { xs: "block", sm: "none" },
          "& .MuiDrawer-paper": {
            boxSizing: "border-box",
            width: drawerWidth,
          },
        }}
      >
        {drawerContent}
      </Drawer>

      {/* Desktop drawer */}
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: "none", sm: "block" },
          "& .MuiDrawer-paper": {
            boxSizing: "border-box",
            width: drawerWidth,
          },
        }}
        open
      >
        {drawerContent}
      </Drawer>
    </Box>
  );
}
