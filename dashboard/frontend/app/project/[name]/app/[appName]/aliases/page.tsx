// This file allows /aliases to work directly without the [app] parameter
// The actual aliases page is at /aliases/[app]/page.tsx
// We import and re-export it here for cleaner URLs

import AliasesPage from "./[app]/page";

export default AliasesPage;

