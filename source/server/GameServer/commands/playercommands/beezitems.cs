namespace DOL.GS.Commands
{
    [CmdAttribute("&beezitems", ePrivLevel.Player, "Acquire Beez's developer items", "/beezitems")]
    public class BeezItemsCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (client.Player != null && !IsSpammingCommand(client.Player, "beezitems"))
                BeezDeveloperItems.Grant(client.Player);
        }
    }
}
