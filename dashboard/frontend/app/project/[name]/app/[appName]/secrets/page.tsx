// This file is intentionally left as a redirect placeholder
// The actual secrets page is at /secrets/[app]/page.tsx
// But we want /secrets to work directly without the [app] parameter
// So we'll import and re-export the actual secrets page component

import SecretsPage from "./[app]/page";

export default SecretsPage;

