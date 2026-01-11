import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Box } from "@mui/material";
import { AppSidebar } from "./AppSidebar";
import { MobileHeader } from "./MobileHeader";
import { Footer } from "./Footer";

const drawerWidth = 240;

export const Layout = () => {
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  return (
    <Box sx={{ display: "flex" }}>
      <AppSidebar
        mobileOpen={mobileOpen}
        onDrawerToggle={handleDrawerToggle}
        drawerWidth={drawerWidth}
      />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <MobileHeader onDrawerToggle={handleDrawerToggle} />
        <Box sx={{ flexGrow: 1, p: { xs: 2, md: 3 } }}>
          <Box sx={{ maxWidth: "1280px", margin: "0 auto" }}>
            <Outlet />
          </Box>
        </Box>
        <Footer />
      </Box>
    </Box>
  );
};
