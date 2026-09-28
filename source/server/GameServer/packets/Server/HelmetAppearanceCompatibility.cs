namespace DOL.GS.PacketHandler
{
    /// <summary>
    /// Presentation-only compatibility for helmet variants that hide the wearer's face in the legacy client.
    /// Item templates, inventory records, and armor properties retain their original extension.
    /// </summary>
    public static class HelmetAppearanceCompatibility
    {
        public static byte VisibleExtension(int slot, int model, byte extension)
        {
            // The Hibernian osnadurtha scale coif renders correctly as model 840 / extension 0,
            // while the same model's extension 2 and 3 variants hide the entire face.
            if (slot == (int)eInventorySlot.HeadArmor && model == 840 &&
                (extension == 2 || extension == 3))
                return 0;

            return extension;
        }
    }
}
