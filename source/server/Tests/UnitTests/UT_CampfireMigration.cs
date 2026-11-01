using System;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using DOL.Database;
using DOL.Database.Handlers;
using DOL.GS;
using NUnit.Framework;

namespace DOL.UnitTests
{
    [TestFixture, NonParallelizable]
    public sealed class UT_CampfireMigration
    {
        private sealed class Server : GameServer
        {
            public IObjectDatabase TestDatabase;
            protected override IObjectDatabase DataBaseImpl => TestDatabase;
        }

        [TestCase(false)] [TestCase(true)]
        public void AddOnlyRegistrationIsIdempotentAndRepairsPartialInstall(bool partial)
        {
            string path = Path.Combine(Path.GetTempPath(), "beez-campfire-" + Guid.NewGuid().ToString("N") + ".db");
            GameServer previous = GameServer.Instance;
            try
            {
                var db = new SqliteObjectDatabase($"Data Source={path};Version=3;Pooling=False;");
                db.RegisterDataObject(typeof(DbItemTemplate));
                db.RegisterDataObject(typeof(DbCoreCharacterXCustomParam));
                db.RegisterDataObject(typeof(DbCoreCharacter));
                db.RegisterDataObject(typeof(DbItemUnique));
                db.RegisterDataObject(typeof(DbInventoryItem));
                var server = (Server)RuntimeHelpers.GetUninitializedObject(typeof(Server));
                server.TestDatabase = db;
                GameServer.LoadTestDouble(server);
                DbCoreCharacter character = new() { Name = "CampfireDataPreservation", AccountName = "test-only", Level = 37, Experience = 1234567 };
                foreach (var property in typeof(DbCoreCharacter).GetProperties(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.DeclaredOnly))
                    if (property.PropertyType == typeof(string) && property.CanWrite && property.GetValue(character) == null)
                        property.SetValue(character, string.Empty);
                Assert.That(db.AddObject(character), Is.True);
                DbItemTemplate unrelated = new() { Id_nb = "test_player_keepsake", Name = "Unrelated original item", Description = "Must remain unchanged", Price = 12345 };
                Assert.That(db.AddObject(unrelated), Is.True);
                if (partial) BeezCampfires.EnsureTemplate();
                BeezCampfires.Load(null, null, EventArgs.Empty);
                BeezCampfires.Load(null, null, EventArgs.Empty);
                Assert.That(db.SelectAllObjects<DbItemTemplate>(), Has.Count.EqualTo(2));
                Assert.That(db.FindObjectByKey<DbItemTemplate>(unrelated.Id_nb).Description, Is.EqualTo(unrelated.Description));
                var savedCharacter = db.SelectAllObjects<DbCoreCharacter>().Single();
                Assert.That(savedCharacter.Level, Is.EqualTo(37));
                Assert.That(savedCharacter.Experience, Is.EqualTo(1234567));
                {
                    var item = db.FindObjectByKey<DbItemTemplate>(BeezCampfires.ItemId);
                    Assert.That(item.MaxCount, Is.EqualTo(1));
                    Assert.That(GameInventoryItem.Create(item), Is.TypeOf<BeezCampfireItem>());
                    Assert.That(item.CanUseEvery, Is.EqualTo(600));
                    Assert.That(item.IsTradable, Is.False);
                    DbInventoryItem inventory = new() { AllowAdd = true, Template = item, ITemplate_Id = item.Id_nb, OwnerID = character.ObjectId, SlotPosition = (int)eInventorySlot.FirstBackpack, Count = 1 };
                    inventory.CanUseAgainIn = 600;
                    Assert.That(db.AddObject(inventory), Is.True);
                    var reloadedDb = new SqliteObjectDatabase($"Data Source={path};Version=3;Pooling=False;");
                    reloadedDb.RegisterDataObject(typeof(DbItemTemplate));
                    reloadedDb.RegisterDataObject(typeof(DbItemUnique));
                    reloadedDb.RegisterDataObject(typeof(DbInventoryItem));
                    var reloaded = reloadedDb.SelectAllObjects<DbInventoryItem>().Single();
                    // The real player's inventory loader makes this call after hydrating template relations.
                    reloaded.SetCooldown();
                    Assert.That(reloaded.CanUseAgainIn, Is.InRange(599, 600));
                    Assert.That(reloaded.Count, Is.EqualTo(1));
                    Assert.That(reloaded.OwnerID, Is.EqualTo(character.ObjectId));
                }
            }
            finally
            {
                GameServer.LoadTestDouble(previous);
                if (File.Exists(path)) File.Delete(path);
            }
        }

        [Test]
        public void CollisionRefusesToOverwriteExistingWorldItem()
        {
            string path = Path.Combine(Path.GetTempPath(), "beez-campfire-collision-" + Guid.NewGuid().ToString("N") + ".db");
            GameServer previous = GameServer.Instance;
            try
            {
                var db = new SqliteObjectDatabase($"Data Source={path};Version=3;Pooling=False;");
                db.RegisterDataObject(typeof(DbItemTemplate));
                var server = (Server)RuntimeHelpers.GetUninitializedObject(typeof(Server));
                server.TestDatabase = db;
                GameServer.LoadTestDouble(server);
                db.AddObject(new DbItemTemplate { Id_nb = BeezCampfires.ItemId, Name = "Existing unrelated item" });
                Assert.Throws<InvalidOperationException>(() => BeezCampfires.EnsureTemplate());
                Assert.That(db.FindObjectByKey<DbItemTemplate>(BeezCampfires.ItemId).Name, Is.EqualTo("Existing unrelated item"));
                Assert.That(db.SelectAllObjects<DbItemTemplate>(), Has.Count.EqualTo(1));
            }
            finally
            {
                GameServer.LoadTestDouble(previous);
                if (File.Exists(path)) File.Delete(path);
            }
        }
    }
}
