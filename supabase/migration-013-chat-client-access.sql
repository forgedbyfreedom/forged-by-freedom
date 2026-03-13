-- Migration 013: Allow clients to create DM channels and add members
-- Previously only org_members (coaches) could create channels and add members.
-- Clients need to be able to start DMs with their coaches.

-- Allow clients to create channels in their org
DROP POLICY IF EXISTS "Coaches can create channels" ON chat_channels;
CREATE POLICY "Authenticated users can create channels in their org"
ON chat_channels FOR INSERT
TO authenticated
WITH CHECK (
  organization_id IN (
    SELECT organization_id FROM org_members WHERE user_id = auth.uid()
  )
  OR
  organization_id IN (
    SELECT organization_id FROM clients WHERE user_id = auth.uid()
  )
);

-- Allow clients to add members to channels in their org
DROP POLICY IF EXISTS "Coaches can add members" ON chat_members;
CREATE POLICY "Org users can add members"
ON chat_members FOR INSERT
TO authenticated
WITH CHECK (
  channel_id IN (
    SELECT cc.id FROM chat_channels cc
    WHERE cc.organization_id IN (
      SELECT organization_id FROM org_members WHERE user_id = auth.uid()
      UNION
      SELECT organization_id FROM clients WHERE user_id = auth.uid()
    )
  )
);
