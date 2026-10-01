import { getUser } from "@/lib/server";
import { AccountSettings } from "@/components/account-settings";

export default async function Settings() {
  const user = await getUser();
  return (
    <div className="account-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">YOUR WORKSPACE, YOUR WAY</p>
          <h1>Settings</h1>
          <p>A few personal touches. A more comfortable place to create.</p>
        </div>
      </header>
      <AccountSettings
        name={user.name}
        email={user.email}
        verified={user.email_verified}
      />
    </div>
  );
}
